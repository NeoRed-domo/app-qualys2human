"""LDAP / Active Directory authentication service (pure, no FastAPI/SQLAlchemy)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ldap3 import Server, Connection, Tls, SUBTREE, ALL_ATTRIBUTES
from ldap3.core.exceptions import LDAPException, LDAPBindError
from ldap3.utils.conv import escape_filter_chars

logger = logging.getLogger("q2h.ldap")


@dataclass
class LdapConfig:
    server_url: str = ""  # ldap://dc.domain.com or ldaps://dc.domain.com
    use_starttls: bool = False
    upn_template: str = "{username}@domain.com"
    search_base: str = ""
    group_attribute: str = "memberOf"
    tls_verify: bool = False  # air-gapped → self-signed certs
    tls_ca_cert: str = ""  # optional path to CA cert


@dataclass
class LdapAuthResult:
    success: bool
    username: str = ""
    display_name: str = ""
    first_name: str = ""
    last_name: str = ""
    groups: list[str] = field(default_factory=list)
    error: str = ""


# Priority order for profile resolution (highest first)
_PROFILE_PRIORITY = ["admin", "user", "monitoring"]


class LdapService:

    @staticmethod
    def _make_server(config: LdapConfig) -> Server:
        use_ssl = config.server_url.lower().startswith("ldaps://")
        tls_obj = None
        if use_ssl or config.use_starttls:
            import ssl

            tls_obj = Tls(
                validate=ssl.CERT_REQUIRED if config.tls_verify else ssl.CERT_NONE,
                ca_certs_file=config.tls_ca_cert or None,
            )
        return Server(config.server_url, use_ssl=use_ssl, tls=tls_obj, get_info=None)

    @staticmethod
    def test_connection(
        config: LdapConfig, username: str, password: str
    ) -> dict:
        """Test a direct bind with the given credentials. Returns {success, message}."""
        try:
            server = LdapService._make_server(config)
            upn = config.upn_template.format(username=username)
            conn = Connection(server, user=upn, password=password, auto_bind=True)
            if config.use_starttls and not config.server_url.lower().startswith("ldaps://"):
                conn.start_tls()
            conn.unbind()
            return {"success": True, "message": f"LDAP_TEST_SUCCESS:{upn}"}
        except LDAPBindError as exc:
            logger.warning("LDAP test bind failed for %s: %s", username, exc)
            return {"success": False, "message": f"LDAP_BIND_FAILED:{exc}"}
        except LDAPException as exc:
            logger.warning("LDAP test connection error: %s", exc)
            return {"success": False, "message": f"LDAP_CONNECTION_ERROR:{exc}"}
        except Exception as exc:
            logger.exception("Unexpected error during LDAP test")
            return {"success": False, "message": f"LDAP_CONNECTION_ERROR:{exc}"}

    @staticmethod
    def authenticate(config: LdapConfig, username: str, password: str) -> LdapAuthResult:
        """Direct bind with user credentials, then search for groups."""
        try:
            server = LdapService._make_server(config)
            upn = config.upn_template.format(username=username)
            conn = Connection(server, user=upn, password=password, auto_bind=True)
            if config.use_starttls and not config.server_url.lower().startswith("ldaps://"):
                conn.start_tls()

            # Search for the user entry to get display name + groups
            search_filter = f"(userPrincipalName={escape_filter_chars(upn)})"
            if not conn.search(
                config.search_base,
                search_filter,
                search_scope=SUBTREE,
                attributes=[ALL_ATTRIBUTES],
            ):
                # Fallback: try sAMAccountName
                search_filter = f"(sAMAccountName={escape_filter_chars(username)})"
                conn.search(
                    config.search_base,
                    search_filter,
                    search_scope=SUBTREE,
                    attributes=[ALL_ATTRIBUTES],
                )

            display_name = username
            first_name = ""
            last_name = ""
            groups: list[str] = []

            if conn.entries:
                entry = conn.entries[0]
                # Display name
                if hasattr(entry, "displayName") and entry.displayName.value:
                    display_name = str(entry.displayName.value)
                elif hasattr(entry, "cn") and entry.cn.value:
                    display_name = str(entry.cn.value)
                # First name (givenName) and last name (sn)
                if hasattr(entry, "givenName") and entry.givenName.value:
                    first_name = str(entry.givenName.value)
                if hasattr(entry, "sn") and entry.sn.value:
                    last_name = str(entry.sn.value)
                # Fallback: split displayName if givenName/sn are empty
                if not first_name and not last_name and display_name != username:
                    parts = display_name.split(None, 1)
                    if len(parts) == 2:
                        first_name, last_name = parts
                    elif len(parts) == 1:
                        first_name = parts[0]
                # Groups
                group_attr = config.group_attribute
                if hasattr(entry, group_attr):
                    raw = getattr(entry, group_attr).values
                    groups = [str(g) for g in raw] if raw else []

            conn.unbind()
            return LdapAuthResult(
                success=True,
                username=username,
                display_name=display_name,
                first_name=first_name,
                last_name=last_name,
                groups=groups,
            )

        except LDAPBindError as exc:
            logger.info("LDAP bind failed for %s: %s", username, exc)
            return LdapAuthResult(success=False, error="INVALID_CREDENTIALS")
        except LDAPException as exc:
            logger.warning("LDAP error during auth for %s: %s", username, exc)
            return LdapAuthResult(success=False, error="LDAP_CONNECTION_ERROR")
        except Exception as exc:
            logger.exception("Unexpected error during LDAP auth")
            return LdapAuthResult(success=False, error="LDAP_CONNECTION_ERROR")

    @staticmethod
    def resolve_profile(
        user_groups: list[str],
        profile_mappings: dict[str, str],
    ) -> str | None:
        """Map AD groups to a profile name. Returns the highest-priority match or None.

        profile_mappings: {profile_name: ad_group_dn}
        Priority: admin > user > monitoring
        Comparison is case-insensitive.
        """
        user_groups_lower = [g.lower() for g in user_groups]
        for profile_name in _PROFILE_PRIORITY:
            ad_dn = profile_mappings.get(profile_name, "")
            if ad_dn and ad_dn.lower() in user_groups_lower:
                return profile_name
        return None
