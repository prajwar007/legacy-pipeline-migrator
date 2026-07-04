Add-Type -AssemblyName System.Drawing

$width = 1600
$height = 1000
$bitmap = [System.Drawing.Bitmap]::new($width, $height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit

$graphics.Clear([System.Drawing.Color]::FromArgb(248, 250, 252))

$titleFont = [System.Drawing.Font]::new("Segoe UI", 30, [System.Drawing.FontStyle]::Bold)
$subtitleFont = [System.Drawing.Font]::new("Segoe UI", 14, [System.Drawing.FontStyle]::Regular)
$nodeFont = [System.Drawing.Font]::new("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
$smallFont = [System.Drawing.Font]::new("Segoe UI", 11, [System.Drawing.FontStyle]::Regular)
$legendFont = [System.Drawing.Font]::new("Segoe UI", 10, [System.Drawing.FontStyle]::Regular)

$ink = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(15, 23, 42))
$muted = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(71, 85, 105))
$bandBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(241, 245, 249))
$bandPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(203, 213, 225), 2)
$arrowPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(51, 65, 85), 3)
$arrowPen.EndCap = [System.Drawing.Drawing2D.LineCap]::ArrowAnchor

function New-RoundedRectanglePath {
    param(
        [float] $X,
        [float] $Y,
        [float] $Width,
        [float] $Height,
        [float] $Radius
    )

    $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
    $path.AddArc($X, $Y, $Radius, $Radius, 180, 90)
    $path.AddArc($X + $Width - $Radius, $Y, $Radius, $Radius, 270, 90)
    $path.AddArc($X + $Width - $Radius, $Y + $Height - $Radius, $Radius, $Radius, 0, 90)
    $path.AddArc($X, $Y + $Height - $Radius, $Radius, $Radius, 90, 90)
    $path.CloseFigure()
    return $path
}

function Draw-Band {
    param(
        [float] $X,
        [float] $Y,
        [float] $Width,
        [float] $Height,
        [string] $Label
    )

    $graphics.FillRectangle($bandBrush, $X, $Y, $Width, $Height)
    $graphics.DrawRectangle($bandPen, $X, $Y, $Width, $Height)
    $graphics.DrawString($Label, $subtitleFont, $muted, $X + 18, $Y + 12)
}

function Draw-Node {
    param(
        [float] $X,
        [float] $Y,
        [float] $Width,
        [float] $Height,
        [string] $Title,
        [string] $Body,
        [System.Drawing.Color] $Fill,
        [System.Drawing.Color] $Border
    )

    $path = New-RoundedRectanglePath -X $X -Y $Y -Width $Width -Height $Height -Radius 18
    $brush = [System.Drawing.SolidBrush]::new($Fill)
    $pen = [System.Drawing.Pen]::new($Border, 2)

    $graphics.FillPath($brush, $path)
    $graphics.DrawPath($pen, $path)

    $titleRect = [System.Drawing.RectangleF]::new($X + 20, $Y + 17, $Width - 40, 30)
    $bodyRect = [System.Drawing.RectangleF]::new($X + 20, $Y + 52, $Width - 40, $Height - 62)
    $graphics.DrawString($Title, $nodeFont, $ink, $titleRect)
    $graphics.DrawString($Body, $smallFont, $muted, $bodyRect)

    $brush.Dispose()
    $pen.Dispose()
    $path.Dispose()
}

function Draw-Arrow {
    param(
        [float] $X1,
        [float] $Y1,
        [float] $X2,
        [float] $Y2
    )

    $graphics.DrawLine($arrowPen, $X1, $Y1, $X2, $Y2)
}

$graphics.DrawString("Legacy Pipeline Migrator Architecture", $titleFont, $ink, 70, 45)
$graphics.DrawString(
    "Perl baseline to Python parser, validation, SFTP ingestion, Oracle load, Airflow orchestration, CI, and operational support",
    $subtitleFont,
    $muted,
    74,
    95
)

Draw-Band 55 150 1490 225 "Source and ingestion"
Draw-Band 55 410 1490 250 "Python pipeline core"
Draw-Band 55 700 1490 230 "Persistence, orchestration, and operations"

Draw-Node 95 220 255 105 "Legacy Perl" "legacy_loader.pl`nReference behavior and gotchas baseline" `
    ([System.Drawing.Color]::FromArgb(224, 242, 254)) ([System.Drawing.Color]::FromArgb(2, 132, 199))
Draw-Node 410 220 255 105 "Input Files" "Pipe-delimited transaction batches from upstream systems" `
    ([System.Drawing.Color]::FromArgb(241, 245, 249)) ([System.Drawing.Color]::FromArgb(100, 116, 139))
Draw-Node 725 220 255 105 "SFTP Poller" "Paramiko client waits for data file plus .done marker" `
    ([System.Drawing.Color]::FromArgb(220, 252, 231)) ([System.Drawing.Color]::FromArgb(22, 163, 74))
Draw-Node 1040 220 255 105 "YAML Config" "Field mapping, validation rules, thresholds, logging" `
    ([System.Drawing.Color]::FromArgb(254, 243, 199)) ([System.Drawing.Color]::FromArgb(217, 119, 6))

Draw-Node 170 485 255 110 "Parse" "Exact field count, delimiter handling, raw record model" `
    ([System.Drawing.Color]::FromArgb(224, 231, 255)) ([System.Drawing.Color]::FromArgb(79, 70, 229))
Draw-Node 500 485 255 110 "Validate" "Account id, txn type, amount, and real date rules" `
    ([System.Drawing.Color]::FromArgb(252, 231, 243)) ([System.Drawing.Color]::FromArgb(219, 39, 119))
Draw-Node 830 485 255 110 "Load Result" "Accepted records, rejected rows, totals, large debit flags" `
    ([System.Drawing.Color]::FromArgb(236, 253, 245)) ([System.Drawing.Color]::FromArgb(5, 150, 105))
Draw-Node 1160 485 255 110 "Oracle Client" "Idempotent MERGE and reconciliation contract" `
    ([System.Drawing.Color]::FromArgb(255, 237, 213)) ([System.Drawing.Color]::FromArgb(234, 88, 12))

Draw-Node 150 755 255 120 "Oracle Tables" "transactions, load_runs, load_errors" `
    ([System.Drawing.Color]::FromArgb(255, 251, 235)) ([System.Drawing.Color]::FromArgb(202, 138, 4))
Draw-Node 470 755 255 120 "Airflow DAG" "Sensor, validate, load, alert with retries" `
    ([System.Drawing.Color]::FromArgb(237, 233, 254)) ([System.Drawing.Color]::FromArgb(124, 58, 237))
Draw-Node 790 755 255 120 "CI/CD" "Ruff, pytest, DAG import check, simulated deploy" `
    ([System.Drawing.Color]::FromArgb(239, 246, 255)) ([System.Drawing.Color]::FromArgb(37, 99, 235))
Draw-Node 1110 755 255 120 "Runbook + Logs" "dictConfig logging and 3am recovery guide" `
    ([System.Drawing.Color]::FromArgb(248, 250, 252)) ([System.Drawing.Color]::FromArgb(71, 85, 105))

Draw-Arrow 350 272 410 272
Draw-Arrow 665 272 725 272
Draw-Arrow 980 272 1040 272
Draw-Arrow 852 325 425 485
Draw-Arrow 350 325 235 485
Draw-Arrow 1095 325 605 485
Draw-Arrow 425 540 500 540
Draw-Arrow 755 540 830 540
Draw-Arrow 1085 540 1160 540
Draw-Arrow 1288 595 405 755
Draw-Arrow 598 755 598 660
Draw-Arrow 725 815 790 815
Draw-Arrow 1045 815 1110 815
Draw-Arrow 1288 755 1288 595

$graphics.DrawString(
    "Generated from repository architecture: docs/architecture_diagram.png",
    $legendFont,
    $muted,
    70,
    955
)

$output = Join-Path (Get-Location) "docs\architecture_diagram.png"
$bitmap.Save($output, [System.Drawing.Imaging.ImageFormat]::Png)

$arrowPen.Dispose()
$bandPen.Dispose()
$bandBrush.Dispose()
$ink.Dispose()
$muted.Dispose()
$titleFont.Dispose()
$subtitleFont.Dispose()
$nodeFont.Dispose()
$smallFont.Dispose()
$legendFont.Dispose()
$graphics.Dispose()
$bitmap.Dispose()
