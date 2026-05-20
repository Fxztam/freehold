class Logger:
    def __init__(self):
        self.file = None
        self.console = True
    def configure(self, file_path=None, console=True):
        self.console = console
        if file_path:
            self.file = open(file_path, "w", encoding="utf-8")
    def log(self, text=""):
        if self.console:
            print(text)
        if self.file:
            self.file.write(text + "\n")
            self.file.flush()

logger = Logger()
def configure_logger(file_path=None, console=True): logger.configure(file_path, console)
def logf(text=""): logger.log(text)
