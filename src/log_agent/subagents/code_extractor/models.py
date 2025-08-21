from pydantic import BaseModel


class CodeUrl(BaseModel):
    status_code: int = 404
    api_url: str|None = None


class CodeSnippets(BaseModel):
    snippets: list[CodeUrl] = []

    def add_snippet(self, snippet: CodeUrl):
        self.snippets.append(snippet)

    def __str__(self):
        return "\n".join([f"[{snippet.api_url}] ({snippet.status_code})" for snippet in self.snippets]) if self.snippets else "No code snippets found."
