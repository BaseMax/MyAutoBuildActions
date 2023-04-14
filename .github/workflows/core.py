class Issue():
    def __init__(self, issue: dict) -> None:
        self.issue = issue
        self.url = None
        self.title = None
        self.user = None
        self.labels = []
        self.state = None
        self.created_at = None
        self.body = None
        self.get_issue_context()

    def get_issue_context(self):
        self.url = self.issue.get('url')
        self.title = self.issue.get('title')
        self.user = self.issue.get('user').get('login')

        for label in self.issue.get('labels'):
            self.labels.append(label.get('name'))

        self.state = self.issue.get('state')
        self.created_at = self.issue.get('created_at')
        self.body = self.issue.get('body')

    def __str__(self) -> str:
        return self.title
