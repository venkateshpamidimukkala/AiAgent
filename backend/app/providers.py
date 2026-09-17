class DispatchProvider:
    """Provider boundary. Replace the demo implementation with OAuth clients."""
    def send(self, source: str, recipient: str, subject: str, body: str) -> str:
        return f"demo-{source}-sent"


dispatch_provider = DispatchProvider()
