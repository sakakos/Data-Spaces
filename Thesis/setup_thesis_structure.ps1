# ============================================================================
# Thesis Structure Setup Script - Plegma Data Space
# ============================================================================
# Χρήση:
#   cd C:\Users\SAKak\Documents\GitHub\Data-Spaces\Thesis
#   .\setup_thesis_structure.ps1
# ============================================================================

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  Thesis Structure Setup" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# Έλεγχος ότι είμαστε στον σωστό φάκελο
Write-Host "Current directory: $(Get-Location)"

if (-not (Test-Path "main.tex")) {
    Write-Host "ERROR: Δεν βρέθηκε main.tex σε αυτόν τον φάκελο!" -ForegroundColor Red
    Write-Host "Πήγαινε πρώτα στον φάκελο Thesis και ξανατρέξε το script." -ForegroundColor Red
    Read-Host "Πάτα Enter για έξοδο"
    exit 1
}

Write-Host "OK: Βρέθηκε main.tex" -ForegroundColor Green
Write-Host ""

# ── Backup παλαιών chapters ───────────────────────────────────────────────
Write-Host "[1/4] Backup παλαιών chapters..." -ForegroundColor Yellow
if (Test-Path "chapters") {
    if (Test-Path "chapters_OLD_backup") {
        Write-Host "      Backup υπάρχει ήδη, παραλείπεται." -ForegroundColor DarkGray
    } else {
        Rename-Item "chapters" "chapters_OLD_backup"
        Write-Host "      Παλιός chapters/ μετονομάστηκε σε chapters_OLD_backup/" -ForegroundColor Green
    }
} else {
    Write-Host "      Δεν υπάρχει chapters/, παραλείπεται." -ForegroundColor DarkGray
}
Write-Host ""

# ── Δημιουργία νέων φακέλων ────────────────────────────────────────────────
Write-Host "[2/4] Δημιουργία φακέλων..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "chapters" | Out-Null
New-Item -ItemType Directory -Force -Path "figures" | Out-Null
New-Item -ItemType Directory -Force -Path "appendices" | Out-Null
Write-Host "      Δημιουργήθηκαν: chapters/, figures/, appendices/" -ForegroundColor Green
Write-Host ""

# ── Δημιουργία αρχείων κεφαλαίων ──────────────────────────────────────────
Write-Host "[3/4] Δημιουργία αρχείων κεφαλαίων..." -ForegroundColor Yellow

$chapters = @(
    "01-introduction|Introduction",
    "02-data-spaces|Theoretical Background: Data Spaces",
    "03-technologies|Technologies and Standards",
    "04-building-blocks|Building Blocks of the Implementation",
    "05-architecture|Architecture of the Plegma Data Space",
    "06-implementation|Implementation and Setup",
    "07-end-to-end-flows|End-to-End Flows",
    "08-demonstration|Access Control Demonstration",
    "09-conclusions|Conclusions and Future Work"
)

foreach ($entry in $chapters) {
    $parts = $entry -split '\|'
    $file = "chapters\$($parts[0]).tex"
    $title = $parts[1]
    $content = "% ====================================================================`n% $title`n% ====================================================================`n`n% TODO: Γράψε το κεφάλαιο εδώ.`n"
    Set-Content -Path $file -Value $content -Encoding UTF8
    Write-Host "      Created: $file" -ForegroundColor Green
}

$appendices = @(
    "A-docker-compose|Docker Compose Files",
    "B-config-files|Configuration Files",
    "C-scripts|Helper Scripts",
    "D-logs|Test Scenario Logs"
)

foreach ($entry in $appendices) {
    $parts = $entry -split '\|'
    $file = "appendices\$($parts[0]).tex"
    $title = $parts[1]
    $content = "% ====================================================================`n% Appendix: $title`n% ====================================================================`n`n% TODO: Συμπλήρωσε το παράρτημα εδώ.`n"
    Set-Content -Path $file -Value $content -Encoding UTF8
    Write-Host "      Created: $file" -ForegroundColor Green
}
Write-Host ""

# ── Backup του παλιού main.tex και δημιουργία νέου ────────────────────────
Write-Host "[4/4] Δημιουργία νέου main.tex..." -ForegroundColor Yellow

if (-not (Test-Path "main.tex.OLD")) {
    Copy-Item "main.tex" "main.tex.OLD"
    Write-Host "      Backup: main.tex -> main.tex.OLD" -ForegroundColor DarkGray
}

$newMain = @'
% !TEX root = main.tex
\documentclass[12pt,a4paper]{report}

\usepackage{template}
\usepackage{tabularx}
\RequirePackage{float}
\RequirePackage{svg}

\usepackage{silence}
\WarningFilter{latex}{Command \showhyphens has changed}
\hbadness=10000
\vbadness=10000

\newcommand{\thesistype}{Diploma Thesis}
\newcommand{\thesistitle}{Experimentation Environment for Data Spaces using FIWARE and i4Trust}
\newcommand{\thesisauthor}{Soterios Kakos}
\newcommand{\thesisyear}{2026}
\renewcommand{\contentsname}{Table of Contents}

\begin{document}

\input{frontmatter/title}
\input{frontmatter/colophon}
\input{frontmatter/dissertation}
\input{frontmatter/committee}
\input{frontmatter/contents}

\clearpage
\pagenumbering{arabic}

\begin{thesischapter}{Introduction}
\input{chapters/01-introduction}
\end{thesischapter}

\begin{thesischapter}{Theoretical Background: Data Spaces}
\input{chapters/02-data-spaces}
\end{thesischapter}

\begin{thesischapter}{Technologies and Standards}
\input{chapters/03-technologies}
\end{thesischapter}

\begin{thesischapter}{Building Blocks of the Implementation}
\input{chapters/04-building-blocks}
\end{thesischapter}

\begin{thesischapter}{Architecture of the Plegma Data Space}
\input{chapters/05-architecture}
\end{thesischapter}

\begin{thesischapter}{Implementation and Setup}
\input{chapters/06-implementation}
\end{thesischapter}

\begin{thesischapter}{End-to-End Flows}
\input{chapters/07-end-to-end-flows}
\end{thesischapter}

\begin{thesischapter}{Access Control Demonstration}
\input{chapters/08-demonstration}
\end{thesischapter}

\begin{thesischapter}{Conclusions and Future Work}
\input{chapters/09-conclusions}
\end{thesischapter}

\appendix
\input{appendices/A-docker-compose}
\input{appendices/B-config-files}
\input{appendices/C-scripts}
\input{appendices/D-logs}

\printbibliography

\end{document}
'@

Set-Content -Path "main.tex" -Value $newMain -Encoding UTF8
Write-Host "      Created: main.tex (νέο)" -ForegroundColor Green
Write-Host ""

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  ΟΛΟΚΛΗΡΩΘΗΚΕ!" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Δημιουργήθηκαν:"
Write-Host "  - 9 κεφάλαια στο chapters/"
Write-Host "  - 4 παραρτήματα στο appendices/"
Write-Host "  - figures/ φάκελος για εικόνες"
Write-Host "  - Νέο main.tex (το παλιό είναι ως main.tex.OLD)"
Write-Host ""
Write-Host "Πάτα Enter για κλείσιμο..."
Read-Host
