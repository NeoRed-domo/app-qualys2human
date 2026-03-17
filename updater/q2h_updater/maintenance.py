# updater/q2h_updater/maintenance.py
"""Static maintenance HTML page -- 4 languages embedded, polls /upgrade-status."""


def get_maintenance_html() -> str:
    """Return the complete maintenance page HTML."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Qualys2Human -- Maintenance</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0a1628; color: #e0e6f0; min-height: 100vh;
    display: flex; align-items: center; justify-content: center;
  }
  .container {
    text-align: center; max-width: 520px; padding: 40px 30px;
    background: #0e1d35; border-radius: 12px;
    border: 1px solid #1c2d44; box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }
  .logo { font-size: 28px; font-weight: 700; color: #1677ff; margin-bottom: 8px; }
  .subtitle { font-size: 14px; color: #8899aa; margin-bottom: 32px; }
  h1 { font-size: 22px; margin-bottom: 24px; }
  .progress-container {
    background: #1c2d44; border-radius: 8px; height: 28px;
    overflow: hidden; margin-bottom: 16px; position: relative;
  }
  .progress-bar {
    height: 100%; background: linear-gradient(90deg, #1677ff, #4096ff);
    border-radius: 8px; transition: width 0.5s ease; min-width: 2%;
  }
  .progress-text {
    position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
    font-size: 13px; font-weight: 600; color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,0.5);
  }
  .step-label { font-size: 14px; color: #8899aa; margin-bottom: 8px; }
  .estimate { font-size: 13px; color: #667788; margin-bottom: 24px; }
  .error-box {
    background: #2a1215; border: 1px solid #ff4d4f; border-radius: 8px;
    padding: 16px; margin-top: 16px; display: none;
  }
  .error-box h3 { color: #ff4d4f; margin-bottom: 8px; }
  .error-box p { font-size: 13px; color: #ffaaaa; }
  .success-box {
    background: #122a15; border: 1px solid #52c41a; border-radius: 8px;
    padding: 16px; margin-top: 16px; display: none;
  }
  .success-box h3 { color: #52c41a; margin-bottom: 8px; }
  .spinner {
    display: inline-block; width: 20px; height: 20px;
    border: 3px solid #1c2d44; border-top-color: #1677ff;
    border-radius: 50%; animation: spin 0.8s linear infinite;
    vertical-align: middle; margin-right: 8px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="container">
  <div class="logo">Qualys2Human</div>
  <div class="subtitle" id="subtitle"></div>
  <h1 id="title"><span class="spinner"></span><span id="titleText"></span></h1>
  <div class="progress-container">
    <div class="progress-bar" id="progressBar" style="width: 0%"></div>
    <div class="progress-text" id="progressText">0%</div>
  </div>
  <div class="step-label" id="stepLabel"></div>
  <div class="estimate" id="estimate"></div>
  <div class="error-box" id="errorBox">
    <h3 id="errorTitle"></h3>
    <p id="errorMsg"></p>
    <p id="errorRestore" style="margin-top:8px;color:#ffdddd;"></p>
  </div>
  <div class="success-box" id="successBox">
    <h3 id="successTitle"></h3>
    <p id="successMsg"></p>
  </div>
</div>
<script>
const i18n = {
  fr: {
    subtitle: "Plateforme de gestion des vulnerabilites",
    title: "Mise a jour en cours...",
    maintenanceTitle: "Maintenance en cours",
    maintenanceMsg: "Veuillez nous excuser pour la gene occasionnee. Nous mettons tout en oeuvre pour remettre le service en etat.",
    step: "Etape {step}/{total} -- {label}",
    estimate: "Temps restant estime : ~{min} min -- indicatif uniquement",
    errorTitle: "Erreur lors de la mise a jour",
    errorRestore: "La version precedente va etre restauree automatiquement.",
    successTitle: "Mise a jour terminee !",
    successMsg: "Redemarrage en cours, redirection automatique...",
    labels: {
      backup_database: "Sauvegarde de la base de donnees",
      backup_files: "Sauvegarde des fichiers",
      extract_package: "Extraction du package",
      run_migrations: "Migration de la base de donnees",
      refresh_matview: "Actualisation des vues",
      restart_service: "Redemarrage du service",
    },
  },
  en: {
    subtitle: "Vulnerability management platform",
    title: "Update in progress...",
    maintenanceTitle: "Maintenance in progress",
    maintenanceMsg: "We apologize for the inconvenience. We are working to restore the service as quickly as possible.",
    step: "Step {step}/{total} -- {label}",
    estimate: "Estimated remaining: ~{min} min -- indicative only",
    errorTitle: "Update failed",
    errorRestore: "The previous version will be restored automatically.",
    successTitle: "Update complete!",
    successMsg: "Restarting, automatic redirect...",
    labels: {
      backup_database: "Backing up database",
      backup_files: "Backing up files",
      extract_package: "Extracting package",
      run_migrations: "Database migration",
      refresh_matview: "Refreshing views",
      restart_service: "Restarting service",
    },
  },
  es: {
    subtitle: "Plataforma de gestion de vulnerabilidades",
    title: "Actualizacion en curso...",
    maintenanceTitle: "Mantenimiento en curso",
    maintenanceMsg: "Le pedimos disculpas por las molestias. Estamos trabajando para restablecer el servicio lo antes posible.",
    step: "Paso {step}/{total} -- {label}",
    estimate: "Tiempo restante estimado: ~{min} min -- solo indicativo",
    errorTitle: "Error en la actualizacion",
    errorRestore: "La version anterior se restaurara automaticamente.",
    successTitle: "Actualizacion completada!",
    successMsg: "Reiniciando, redireccion automatica...",
    labels: {
      backup_database: "Respaldando base de datos",
      backup_files: "Respaldando archivos",
      extract_package: "Extrayendo paquete",
      run_migrations: "Migracion de base de datos",
      refresh_matview: "Actualizando vistas",
      restart_service: "Reiniciando servicio",
    },
  },
  de: {
    subtitle: "Schwachstellenmanagement-Plattform",
    title: "Update wird durchgefuhrt...",
    maintenanceTitle: "Wartung wird durchgefuhrt",
    maintenanceMsg: "Wir entschuldigen uns fur die Unannehmlichkeiten. Wir arbeiten daran, den Dienst so schnell wie moglich wiederherzustellen.",
    step: "Schritt {step}/{total} -- {label}",
    estimate: "Geschatzte Restzeit: ~{min} Min -- nur indikativ",
    errorTitle: "Update fehlgeschlagen",
    errorRestore: "Die vorherige Version wird automatisch wiederhergestellt.",
    successTitle: "Update abgeschlossen!",
    successMsg: "Neustart, automatische Weiterleitung...",
    labels: {
      backup_database: "Datenbank sichern",
      backup_files: "Dateien sichern",
      extract_package: "Paket entpacken",
      run_migrations: "Datenbankmigration",
      refresh_matview: "Ansichten aktualisieren",
      restart_service: "Dienst neustarten",
    },
  },
};

// Detect language
const userLang = (navigator.language || "en").slice(0, 2).toLowerCase();
const t = i18n[userLang] || i18n.en;

document.getElementById("subtitle").textContent = t.subtitle;
document.getElementById("titleText").textContent = t.title;

let redirectTimer = null;
let maintenanceMode = false;

function updateUI(data) {
  const bar = document.getElementById("progressBar");
  const pText = document.getElementById("progressText");
  const stepLabel = document.getElementById("stepLabel");
  const estimate = document.getElementById("estimate");

  // Detect maintenance mode (no upgrade in progress — pending with step 0 persists)
  if (data.state === "pending" && data.percent === 0 && !maintenanceMode) {
    // After 3 polls with no progress, switch to maintenance mode display
    if (!window._pendingCount) window._pendingCount = 0;
    window._pendingCount++;
    if (window._pendingCount >= 2) {
      maintenanceMode = true;
      document.querySelector(".spinner").style.display = "none";
      document.getElementById("titleText").textContent = t.maintenanceTitle || t.title;
      stepLabel.textContent = t.maintenanceMsg || "";
      bar.style.width = "0%";
      pText.textContent = "";
      document.querySelector(".progress-container").style.display = "none";
      estimate.textContent = "";
      return;
    }
  }

  if (maintenanceMode) return;

  bar.style.width = data.percent + "%";
  pText.textContent = data.percent + "%";

  if (data.state === "running") {
    const label = (t.labels && t.labels[data.step_label]) || data.step_label;
    stepLabel.textContent = t.step
      .replace("{step}", data.step)
      .replace("{total}", data.total_steps)
      .replace("{label}", label);
    if (data.estimated_remaining_minutes > 0) {
      estimate.textContent = t.estimate.replace("{min}", data.estimated_remaining_minutes);
    } else {
      estimate.textContent = "";
    }
  } else if (data.state === "complete") {
    document.querySelector(".spinner").style.display = "none";
    document.getElementById("titleText").textContent = "";
    stepLabel.textContent = "";
    estimate.textContent = "";
    bar.style.width = "100%";
    pText.textContent = "100%";
    const successBox = document.getElementById("successBox");
    successBox.style.display = "block";
    document.getElementById("successTitle").textContent = t.successTitle;
    document.getElementById("successMsg").textContent = t.successMsg.replace("{sec}", "...");
    // Poll the app until it responds, then redirect
    function tryRedirect() {
      fetch("/api/health", { signal: AbortSignal.timeout(3000) })
        .then(r => { if (r.ok) window.location.href = "/"; else setTimeout(tryRedirect, 3000); })
        .catch(() => setTimeout(tryRedirect, 3000));
    }
    setTimeout(tryRedirect, 5000);
  } else if (data.state === "failed") {
    document.querySelector(".spinner").style.display = "none";
    document.getElementById("titleText").textContent = "";
    stepLabel.textContent = "";
    estimate.textContent = "";
    bar.style.background = "#ff4d4f";
    const errorBox = document.getElementById("errorBox");
    errorBox.style.display = "block";
    document.getElementById("errorTitle").textContent = t.errorTitle;
    document.getElementById("errorMsg").textContent = data.error || "Unknown error";
    document.getElementById("errorRestore").textContent = t.errorRestore;
  }
}

function poll() {
  fetch("/upgrade-status")
    .then(r => r.json())
    .then(data => {
      updateUI(data);
      if (data.state !== "complete" && data.state !== "failed") {
        setTimeout(poll, 2000);
      }
    })
    .catch(() => setTimeout(poll, 2000));
}

poll();
</script>
</body>
</html>'''
