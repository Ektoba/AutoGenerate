class ConfigValidator:
    def __init__(self, config):
        self.config = config
    def validate(self):
        errors = []
        if 'MainVcxprojPath' not in self.config:
            errors.append("MainVcxprojPath가 없음")
        # 필요한 다른 필드들도 검증...
        return errors
