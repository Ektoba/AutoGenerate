# ----------------------------------------------------
# config.json 파일 자동 업데이트 스크립트 (PowerShell)
# - 프로젝트 루트 경로 및 UE 설치 경로 자동 탐색 및 업데이트
# - UnrealEngineRootPath 필드 추가 및 저장
# - PowerShell 5.1 호환성 강화
# - MainVcxprojPath 필드 추가 및 저장 로직 강화
# - 중괄호 오류 수정
# - .vcxproj 파일 재귀 탐색 강화 (Intermediate 폴더 내에서도 찾도록)
# ----------------------------------------------------

# 스크립트가 위치한 디렉토리 (AutoGenerate 폴더)를 기준으로 작업
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ConfigFilePath = Join-Path -Path $ScriptDir -ChildPath "config.json"


# 상대경로 변환 함수 필요 (스크립트 상단에 추가)
function Get-RelativePath($Path, $BasePath) {
    $cleanBase = (Resolve-Path -LiteralPath $BasePath).ProviderPath.TrimEnd('\')
    $cleanPath = (Resolve-Path -LiteralPath $Path).ProviderPath.TrimEnd('\')
    $uriBase = New-Object System.Uri($cleanBase + '\')
    $uriPath = New-Object System.Uri($cleanPath)
    $relativeUri = $uriBase.MakeRelativeUri($uriPath)
    $relativePath = [System.Uri]::UnescapeDataString($relativeUri.ToString())
    return $relativePath -replace '/', '\'
}


Write-Host "--- config.json 자동 업데이트 스크립트 시작 ---" -ForegroundColor Yellow

# 기존 config.json 파일 로드 또는 새 JSON 객체 생성
$Config = $null
if (Test-Path $ConfigFilePath) {
    try {
        $Config = Get-Content $ConfigFilePath | ConvertFrom-Json -ErrorAction Stop
        Write-Host "[INFO] 기존 config.json 파일을 로드했습니다." -ForegroundColor DarkCyan
    }
    catch {
        Write-Host "[WARNING] 기존 config.json 파일을 읽거나 파싱하는데 실패했습니다. 새 파일을 생성합니다." -ForegroundColor Yellow
        $Config = New-Object PSObject
    }
} else {
    Write-Host "[INFO] config.json 파일이 없어 새 파일을 생성합니다." -ForegroundColor Cyan
    $Config = New-Object PSObject
}

# config.json에 필요한 필드가 없으면 동적으로 추가 (PowerShell 5.1 호환성 개선)
if (-not ($Config | Get-Member -Name "ProjectRootPath" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $Config | Add-Member -MemberType NoteProperty -Name "ProjectRootPath" -Value ".."
}
if (-not ($Config | Get-Member -Name "UnrealEngineVersion" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $Config | Add-Member -MemberType NoteProperty -Name "UnrealEngineVersion" -Value "5.5"
}
if (-not ($Config | Get-Member -Name "UnrealEngineRootPath" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $Config | Add-Member -MemberType NoteProperty -Name "UnrealEngineRootPath" -Value ""
}
if (-not ($Config | Get-Member -Name "MainVcxprojPath" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    Write-Host "[INFO] 'MainVcxprojPath' 필드를 config.json에 추가합니다." -ForegroundColor DarkGray
    $Config | Add-Member -MemberType NoteProperty -Name "MainVcxprojPath" -Value ""
}
if (-not ($Config | Get-Member -Name "MainVcxprojFiltersPath" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    Write-Host "[INFO] 'MainVcxprojFiltersPath' 필드를 config.json에 추가합니다." -ForegroundColor DarkGray
    $Config | Add-Member -MemberType NoteProperty -Name "MainVcxprojFiltersPath" -Value ""
}
if (-not ($Config | Get-Member -Name "LogPath" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    Write-Host "[INFO] 'LogPath' 필드를 config.json에 추가합니다." -ForegroundColor DarkGray
    $Config | Add-Member -MemberType NoteProperty -Name "LogPath" -Value "Logs\Watcher.log"
}
if (-not ($Config | Get-Member -Name "WatchPaths" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $Config | Add-Member -MemberType NoteProperty -Name "WatchPaths" -Value @("Source", "Plugins")
}
if (-not ($Config | Get-Member -Name "WatchFileExtensions" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $Config | Add-Member -MemberType NoteProperty -Name "WatchFileExtensions" -Value @(".cpp", ".h", ".hpp", ".c", ".inl")
}
if (-not ($Config | Get-Member -Name "GenerateScript" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $Config | Add-Member -MemberType NoteProperty -Name "GenerateScript" -Value "GenerateProjectFile.ps1"
}
if (-not ($Config | Get-Member -Name "DebounceTimeForModifiedMs" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $Config | Add-Member -MemberType NoteProperty -Name "DebounceTimeForModifiedMs" -Value 1500
}
if (-not ($Config | Get-Member -Name "DryRun" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $Config | Add-Member -MemberType NoteProperty -Name "DryRun" -Value $true # 기본값은 true (안전하게)
}
if (-not ($Config | Get-Member -Name "DebounceTimeForOtherEventsMs" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $Config | Add-Member -MemberType NoteProperty -Name "DebounceTimeForOtherEventsMs" -Value 1500
}
if (-not ($Config | Get-Member -Name "MainUprojectPath" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $Config | Add-Member -MemberType NoteProperty -Name "MainUprojectPath" -Value "EMBER.uproject"
}
if (-not ($Config | Get-Member -Name "IgnoredNamePatterns" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $IgnoredPatterns = @(
        ".obj", ".pdb", ".tmp", ".user", ".log", ".ilk", ".ipch", ".sdf",
        ".vs", ".VC.opendb", ".suo", ".ncb", ".bak", "~", ".swp", ".lock"
    )
    $Config | Add-Member -MemberType NoteProperty -Name "IgnoredNamePatterns" -Value $IgnoredPatterns
}

if (-not ($Config | Get-Member -Name "IgnoredDirs" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    # '/intermediate/'는 여기서 제외하는 게 중요해! .vcxproj 파일이 무시될 수 있기 때문이지. 😉
    $IgnoredDirectories = @(
        "/saved/", "/binaries/", "/build/", "/deriveddata/", "/staging/",
        "/unrealbuildtool/", "/logs/", "/backup/"
    )
    $Config | Add-Member -MemberType NoteProperty -Name "IgnoredDirs" -Value $IgnoredDirectories
}

if (-not ($Config | Get-Member -Name "BackupDir" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $Config | Add-Member -MemberType NoteProperty -Name "BackupDir" -Value "backup"
}
if (-not ($Config | Get-Member -Name "PatrolIntervalMinutes" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $Config | Add-Member -MemberType NoteProperty -Name "PatrolIntervalMinutes" -Value 30 # 기본 30분
}
# --- 1. 프로젝트 루트 경로 찾기 ---
Write-Host "[INFO] 프로젝트 루트를 탐색합니다..." -ForegroundColor Cyan
$projectRoot = $null
$currentSearchDir = $ScriptDir

$uprojectFileFound = $null
for ($i = 0; $i -lt 5; $i++) {
    $uprojectFiles = Get-ChildItem -Path $currentSearchDir -Filter "*.uproject" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($uprojectFiles) {
        $uprojectFileFound = $uprojectFiles
		$Config.MainUprojectPath = $uprojectFileFound.Name
		$projectRoot = (Get-Item $currentSearchDir).FullName
        break
    }
	
    $parentDir = Split-Path -Parent $currentSearchDir
	
    if ($parentDir -eq $currentSearchDir) {
        break
    }
    $currentSearchDir = $parentDir
}

if ($projectRoot) {
	Write-Host "[DEBUG] projectRoot의 경로 : $projectRoot" -ForegroundColor Red
    $relativePath = ".."
    if ($projectRoot -eq $ScriptDir) { $relativePath = "." }
    elseif ($projectRoot.StartsWith($ScriptDir + "\")) { $relativePath = (Get-Item -Path $projectRoot).Name }
    $Config.ProjectRootPath = $relativePath
    Write-Host "[INFO] 프로젝트 루트를 찾았습니다: $projectRoot (config.json에 '$($Config.ProjectRootPath)'로 저장)" -ForegroundColor Green

    # --- .uproject 파일 기준 메인 .vcxproj, .filters 찾기 ---
	if ($uprojectFileFound) {
		$uprojectFileNameBase = $uprojectFileFound.BaseName
		$mainVcxprojName = "$uprojectFileNameBase.vcxproj"
		$mainVcxprojFiltersName = "$uprojectFileNameBase.vcxproj.filters"

		# .vcxproj 찾기
		$foundVcxproj = Get-ChildItem -Path $projectRoot -Filter "$mainVcxprojName" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
		# .vcxproj.filters 찾기
		$foundVcxprojFilters = Get-ChildItem -Path $projectRoot -Filter "$mainVcxprojFiltersName" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1

		# .vcxproj 상대경로 저장
		if ($foundVcxproj) {
			$relativeVcxproj = Get-RelativePath $foundVcxproj.FullName $projectRoot
			Write-Host "[DEBUG] relativeVcxproj 경로 : $relativeVcxproj" -ForegroundColor Red
			$Config.MainVcxprojPath = $relativeVcxproj
			Write-Host "[INFO] 메인 .vcxproj 파일을 찾았습니다: $($relativeVcxproj) (config.json에 상대경로로 저장)" -ForegroundColor Green
		} else {
			$Config.MainVcxprojPath = ""
			Write-Host "[WARNING] 메인 .vcxproj 파일을 못 찾았습니다." -ForegroundColor Yellow
		}

		# .vcxproj.filters 상대경로 저장
		if ($foundVcxprojFilters) {
			$relativeVcxprojFilters = Get-RelativePath $foundVcxprojFilters.FullName $projectRoot
			Write-Host "[DEBUG] VcxprojFilters 경로 : $relativeVcxprojFilters" -ForegroundColor Red
			$Config.MainVcxprojFiltersPath = $relativeVcxprojFilters
			Write-Host "[INFO] 메인 .vcxproj.filters 파일을 찾았습니다: $($relativeVcxprojFilters) (config.json에 상대경로로 저장)" -ForegroundColor Green
		} else {
			$Config.MainVcxprojFiltersPath = ""
			Write-Host "[WARNING] 메인 .vcxproj.filters 파일을 못 찾았습니다." -ForegroundColor Yellow
		}
	}

} else {
    Write-Host "[WARNING] 프로젝트 루트 ('.uproject' 파일 포함 디렉토리)를 찾을 수 없습니다. config.json의 ProjectRootPath를 수동으로 확인해주세요." -ForegroundColor Yellow
    if (-not $Config.ProjectRootPath) { $Config.ProjectRootPath = ".." }
    $Config.MainVcxprojPath = ""
}

# --- 2. 언리얼 엔진 설치 경로 찾기 ---
Write-Host "[INFO] 언리얼 엔진 설치 경로를 탐색합니다... (버전: $($Config.UnrealEngineVersion))" -ForegroundColor Cyan
$detectedEnginePath = $null
$engineVersion = $Config.UnrealEngineVersion

try {
    $regPath = "HKLM:\SOFTWARE\EpicGames\Unreal Engine\$engineVersion"
    $detectedEnginePath = Get-ItemPropertyValue -Path $regPath -Name InstalledDirectory -ErrorAction SilentlyContinue
    if (-not (Test-Path $detectedEnginePath)) {
        $detectedEnginePath = $null
    }
}
catch {
    Write-Host "[INFO] 레지스트리에서 UE $engineVersion 경로를 찾을 수 없습니다. 기본 경로를 시도합니다." -ForegroundColor DarkCyan
}

if (-not $detectedEnginePath) {
    $defaultPath = "C:\Program Files\Epic Games\UE_$engineVersion"
    if (Test-Path $defaultPath) {
        $detectedEnginePath = $defaultPath
    } else {
        Write-Host "[WARNING] 기본 경로에서도 UE $engineVersion 설치 경로를 찾을 수 없습니다. config.json의 UnrealEngineRootPath를 수동으로 설정해야 할 수 있습니다." -ForegroundColor Yellow
    }
}

if ($detectedEnginePath) {
    $Config.UnrealEngineRootPath = $detectedEnginePath
    Write-Host "[INFO] 감지된 UE 엔진 경로: $($Config.UnrealEngineRootPath) (config.json에 저장)" -ForegroundColor Green
} else {
    $Config.UnrealEngineRootPath = ""
    Write-Host "[WARNING] Unreal Engine Root Path를 config.json에 저장하지 못했습니다. 수동으로 입력해주세요." -ForegroundColor Yellow
}

# --- 3. 업데이트된 설정 저장 ---
Write-Host "`n[INFO] config.json 파일을 업데이트합니다..." -ForegroundColor Yellow
try {
    $jsonStr = $Config | ConvertTo-Json -Depth 4
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)  # $false = no BOM
    $sw = New-Object System.IO.StreamWriter($ConfigFilePath, $false, $utf8NoBom)
    $sw.Write($jsonStr)
    $sw.Close()
    Write-Host "[SUCCESS] config.json 파일이 BOM 없이 UTF-8로 저장되었습니다: $ConfigFilePath" -ForegroundColor Green
    Write-Host "설정 파일 내용을 확인하고 필요에 따라 수정해주세요." -ForegroundColor Green
}
catch {
    Write-Host "[ERROR] config.json 파일 저장 중 오류 발생: $($_.Exception.Message) 😢" -ForegroundColor Red
}

Write-Host "`n--- config.json 자동 업데이트 스크립트 종료 ---" -ForegroundColor Yellow