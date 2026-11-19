class MockSMTP:
    def __init__(self,*args,**kwargs):pass
    def starttls(self):pass
    def login(self,*args):pass
    def send_message(self,*args):pass
    def __enter__(self):return self
    def __exit__(self,*args):return False
