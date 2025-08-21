import os
import requests

def load_code_snippets(code_urls: list[str]):
    """
    Load code snippets from the provided URLs.

    Args:
        code_urls

    Returns:
        dict: Dictionary with URL as key and code snippet as value.
    """
    code_snippets = {}
    for url in code_urls:
        try:
            private_token = os.environ.get("GITLAB_TOKEN")
            headers = {"PRIVATE-TOKEN": private_token}
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                code_snippets[url] = response.text
            else:
                print(f"Failed to fetch {url}: HTTP {response.status_code}")
        except Exception as e:
            print(f"Error fetching {url}: {e}")

    return code_snippets