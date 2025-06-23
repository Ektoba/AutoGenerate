class ConfigValidator:
    def __init__(self, config):
        self.config = config

    def validate(self):
        errors = []
        # 필수 필드 목록
        required_fields = [
            "MainVcxprojPath",
            "MainVcxprojFiltersPath",
            "ProjectRootPath",
            "UnrealEngineRootPath",
            "WatchPaths",
            "WatchFileExtensions",
            "GenerateScript"
        ]
        for field in required_fields:
            if field not in self.config or not self.config[field]:
                errors.append(f"필수 설정 누락: {field}")

        # 타입 검사
        if not isinstance(self.config.get("WatchPaths", []), list):
            errors.append("WatchPaths는 리스트여야 합니다.")
        if not isinstance(self.config.get("WatchFileExtensions", []), list):
            errors.append("WatchFileExtensions는 리스트여야 합니다.")

        # 백업 폴더 경로 존재 검사(선택)
        backup_dir = self.config.get("BackupDir")
        if backup_dir and not isinstance(backup_dir, str):
            errors.append("BackupDir은 문자열이어야 합니다.")

        return errors
