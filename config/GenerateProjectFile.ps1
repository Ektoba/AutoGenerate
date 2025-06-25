# ------------------------------
# UE5.5용 VS 프로젝트 자동 생성 스크립트 (PowerShell)
# - config.json에서 언리얼 엔진 경로를 읽어와 사용
# - config.json의 UnrealEngineRootPath가 비어있을 때만 엔진 경로 탐색
# - PowerShell 5.1 호환성 강화
# ------------------------------

# 스크립트가 위치한 디렉토리를 AutoGenerate 폴더로 간주
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ConfigFilePath = Join-Path -Path $ScriptDir -ChildPath "config.json"

# 1. .uproject 파일 자동 감지 (ScriptDir 기준, config.json의 ProjectRootPath는 사용하지 않음)
# 이 스크립트 자체는 프로젝트 루트가 현재 폴더의 상위 폴더에 있다고 가정
$projectRoot = $ScriptDir | Split-Path -Parent # AutoGenerate 폴더의 부모가 프로젝트 루트
$uprojectFile = Get-ChildItem -Path $projectRoot -Filter "*.uproject" | Select-Object -First 1

if (-not $uprojectFile) {
    Write-Host "[ERROR] 프로젝트 루트 ($projectRoot)에서 .uproject 파일을 찾을 수 없습니다!" -ForegroundColor Red
    exit 1
}
Write-Host "[INFO] 프로젝트 파일을 찾았습니다: $($uprojectFile.Name)" -ForegroundColor Green

# --- config.json 파일 로드 ---
$Config = $null
if (Test-Path $ConfigFilePath) {
    try {
        $Config = Get-Content $ConfigFilePath | ConvertFrom-Json -ErrorAction SilentlyContinue
    }
    catch {
        Write-Host "[WARNING] config.json 파일을 읽거나 파싱하는데 실패했습니다. 일부 설정이 기본값으로 사용될 수 있습니다." -ForegroundColor Yellow
        # 파일 파싱 실패 시, Config를 null로 유지하여 아래에서 기본값 할당
    }
}

# config.json이 없거나 필요한 필드가 없으면 기본값 설정 (PowerShell 5.1 호환성 개선)
if (-not $Config) {
    $Config = New-Object PSObject
}

# UnrealEngineRootPath 필드 확인 및 추가 (if not exists)
if (-not ($Config | Get-Member -Name "UnrealEngineRootPath" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $Config | Add-Member -MemberType NoteProperty -Name "UnrealEngineRootPath" -Value ""
}
# UnrealEngineVersion 필드 확인 및 추가 (if not exists)
if (-not ($Config | Get-Member -Name "UnrealEngineVersion" -MemberType NoteProperty -ErrorAction SilentlyContinue)) {
    $Config | Add-Member -MemberType NoteProperty -Name "UnrealEngineVersion" -Value "5.5"
}

$engineVersion = $Config.UnrealEngineVersion
$configuredEnginePath = $Config.UnrealEngineRootPath

# 2. UE 설치 경로 탐색 (config.json의 UnrealEngineRootPath 우선, 비어있거나 유효하지 않으면 탐색)
Write-Host "[INFO] 언리얼 엔진 설치 경로를 탐색합니다... (UE $engineVersion)" -ForegroundColor Cyan
$enginePath = $null

# config.json의 UnrealEngineRootPath가 비어있지 않고 유효한지 먼저 확인
if (-not ([string]::IsNullOrEmpty($configuredEnginePath)) -and (Test-Path $configuredEnginePath)) {
    $enginePath = $configuredEnginePath
    Write-Host "[INFO] config.json에서 엔진 경로를 로드했습니다: $enginePath" -ForegroundColor Green
} else {
    Write-Host "[INFO] config.json의 UnrealEngineRootPath가 비어있거나 유효하지 않아 엔진 경로를 탐색합니다." -ForegroundColor DarkCyan
    
    # 레지스트리 탐색
    try {
        $regPath = "HKLM:\SOFTWARE\EpicGames\Unreal Engine\$engineVersion"
        $enginePath = Get-ItemPropertyValue -Path $regPath -Name InstalledDirectory -ErrorAction SilentlyContinue
        if (-not (Test-Path $enginePath)) { # 레지스트리에 경로가 있어도 실제 폴더가 없으면 무효
            $enginePath = $null
        }
    }
    catch {
        Write-Host "[INFO] 레지스트리에서 UE $engineVersion 경로를 찾을 수 없습니다. 기본 경로를 시도합니다." -ForegroundColor DarkCyan
    }

    # 기본 경로 탐색
    if (-not $enginePath) {
        $defaultPath = "C:\Program Files\Epic Games\UE_$engineVersion"
        if (Test-Path $defaultPath) {
            $enginePath = $defaultPath
            Write-Host "[INFO] 기본 경로에서 UE $engineVersion 경로를 찾았습니다: $defaultPath" -ForegroundColor Green
        }
    }

    # 탐색 후에도 경로를 찾지 못했으면 오류 메시지 출력
    if ([string]::IsNullOrEmpty($enginePath) -or !(Test-Path $enginePath)) {
        Write-Host "[ERROR] Unreal Engine $engineVersion 설치 경로를 자동으로 찾을 수 없습니다! config.json의 'UnrealEngineRootPath'를 수동으로 설정해주세요." -ForegroundColor Red
        exit 2 
    }
}

Write-Host "[INFO] 최종 엔진 경로: $enginePath" -ForegroundColor Green

# 3. UnrealBuildTool.dll 경로 설정
$ubtPath = Join-Path -Path $enginePath -ChildPath "Engine\Binaries\DotNET\UnrealBuildTool"
$ubtDll  = Join-Path -Path $ubtPath -ChildPath "UnrealBuildTool.dll"

if (!(Test-Path $ubtDll)) {
    Write-Host "[ERROR] UnrealBuildTool.dll 파일을 찾을 수 없습니다! 경로: $ubtDll" -ForegroundColor Red
    exit 3
}

# 4. dotnet 명령으로 프로젝트 파일 생성
Write-Host "`n[INFO] VS 프로젝트 파일 생성 중..." -ForegroundColor Yellow
$uprojectFullPath = $uprojectFile.FullName
Push-Location $ubtPath
$cmd = "dotnet UnrealBuildTool.dll -projectfiles -project=`"$uprojectFullPath`" -game -engine"

Write-Host "[실행]: $cmd" -ForegroundColor Yellow

# 실제 실행
Invoke-Expression $cmd

Pop-Location

Write-Host "`n[완료] VS 프로젝트 파일이 갱신되었습니다!" -ForegroundColor Green