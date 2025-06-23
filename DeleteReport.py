class DeleteReport:
    def __init__(self):
        self.deleted = []
        self.failed = []
        self.dryrun = []

    def add_deleted(self, path): self.deleted.append(path)
    def add_failed(self, path): self.failed.append(path)
    def add_dryrun(self, path): self.dryrun.append(path)

    def summary(self, to_file=None):
        report = []
        report.append(f"[REPORT] 삭제 성공 {len(self.deleted)}건, 실패 {len(self.failed)}건, DryRun {len(self.dryrun)}건")
        if self.deleted:
            report.append(" - 삭제 성공 파일 목록:")
            for f in self.deleted:
                report.append(f"    {f}")
        if self.failed:
            report.append(" - 삭제 실패 파일 목록:")
            for f in self.failed:
                report.append(f"    {f}")
        if self.dryrun:
            report.append(" - DryRun 파일 목록:")
            for f in self.dryrun:
                report.append(f"    {f}")

        if to_file:
            try:
                with open(to_file, "a", encoding="utf-8") as f:
                    f.write("\n".join(report) + "\n")
            except Exception as e:
                print(f"[DeleteReport] 리포트 파일 저장 실패: {e}")

        print("\n".join(report))
