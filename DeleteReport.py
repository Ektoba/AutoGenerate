class DeleteReport:
    def __init__(self):
        self.deleted = []
        self.failed = []
        self.dryrun = []

    def add_deleted(self, path): self.deleted.append(path)
    def add_failed(self, path): self.failed.append(path)
    def add_dryrun(self, path): self.dryrun.append(path)

    def summary(self):
        print(f"[REPORT] 삭제 성공 {len(self.deleted)}건, 실패 {len(self.failed)}건, DryRun {len(self.dryrun)}건")
        if self.deleted:
            print(" - 삭제 성공 파일 목록:")
            for f in self.deleted: print("   ", f)
        if self.failed:
            print(" - 삭제 실패 파일 목록:")
            for f in self.failed: print("   ", f)
        if self.dryrun:
            print(" - DryRun 파일 목록:")
            for f in self.dryrun: print("   ", f)
