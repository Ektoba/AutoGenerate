import os
# import sys # sys 모듈은 필요 없으므로 제거 (AppLogger 사용)

class DeleteReport:
    def __init__(self, logger=None): # logger 인자 추가
        self.deleted = []
        self.failed = []
        self.dryrun = []
        self.logger = logger # logger 저장 (main에서 주입)

    def add_deleted(self, path): self.deleted.append(path)
    def add_failed(self, path): self.failed.append(path)
    def add_dryrun(self, path): self.dryrun.append(path)

    def summary(self, to_file=None):
        report_lines = []
        report_lines.append(f"[REPORT] 삭제 성공 {len(self.deleted)}건, 실패 {len(self.failed)}건, DryRun {len(self.dryrun)}건")
        if self.deleted:
            report_lines.append(" - 삭제 성공 파일 목록:")
            for f in self.deleted:
                report_lines.append(f"    {f}")
        if self.failed:
            report_lines.append(" - 삭제 실패 파일 목록:")
            for f in self.failed:
                report_lines.append(f"    {f}")
        if self.dryrun:
            report_lines.append(" - DryRun 파일 목록:")
            for f in self.dryrun:
                report_lines.append(f"    {f}")

        # 모든 리포트 라인을 logger.info로 전달 (콘솔과 파일 모두에 출력)
        if self.logger:
            for line in report_lines:
                self.logger.info(line)
        else: # logger가 없다면 기존처럼 print 사용 (최후의 보루)
            print("\n".join(report_lines))


        if to_file:
            try:
                # 리포트 파일에는 모든 상세 내용을 기록하기 위해 직접 쓰기
                with open(to_file, "a", encoding="utf-8") as f:
                    f.write("\n".join(report_lines) + "\n")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"[DeleteReport] 리포트 파일 저장 실패: {e}", exc_info=True) # exc_info=True 추가
                else:
                    print(f"[DeleteReport] 리포트 파일 저장 실패: {e}")