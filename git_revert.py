import requests
import base64
import sys

class GitHubReverter:
    """
    A class to handle the process of reverting the latest commit or rolling back a specific file in a GitHub Enterprise repository.
    """

    def __init__(self, token, organization, repo_name, branch, enterprise_domain):
        """
        Initializes the GitHubReverter with the required details for interacting with the GitHub Enterprise API.
        """
        self.token = token
        self.organization = organization
        self.repo_name = repo_name
        self.branch = branch
        self.enterprise_domain = enterprise_domain
        self.api_url = f'https://{self.enterprise_domain}/api/v3/repos/{self.organization}/{self.repo_name}'
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.error_found = False

    def get_commit_details(self, commit_sha):
        """Fetches details for a specific commit."""
        url = f'{self.api_url}/commits/{commit_sha}'
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching commit details: {response.status_code}")
            self.error_found = True
            return None

    def get_latest_commit_sha(self):
        """Retrieves the SHA of the latest commit on the branch."""
        url = f'{self.api_url}/commits/{self.branch}'
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json()['sha']
        else:
            print(f"Error fetching the latest commit on {self.branch}: {response.status_code}")
            self.error_found = True
            return None

    def get_previous_commit_sha_for_file(self, file_path):
        """Retrieves the SHA of the commit where the file was last modified before the latest commit."""
        url = f'{self.api_url}/commits'
        params = {
            'path': file_path,
            'sha': self.branch,
            'per_page': 2  # Get the last two commits for this file
        }
        response = requests.get(url, params=params, headers=self.headers)
        if response.status_code == 200:
            commits = response.json()
            if len(commits) > 1:
                return commits[1]['sha']  # The second commit is the previous version
            else:
                print("There is no previous version of this file in the history.")
                self.error_found = True
                return None
        else:
            print(f"Error retrieving commit history: {response.status_code}")
            self.error_found = True
            return None

    def get_file_contents(self, file_path, commit_sha):
        """Fetches the contents of a file at a specific commit."""
        url = f'{self.api_url}/contents/{file_path}?ref={commit_sha}'
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            content = base64.b64decode(response.json()['content']).decode('utf-8')
            return content, response.json()['sha']
        else:
            print(f"Error fetching file contents: {response.status_code}")
            self.error_found = True
            return None, None

    def update_file_contents(self, file_path, new_content, commit_message, sha):
        """Updates the file in the repository with the new content."""
        url = f'{self.api_url}/contents/{file_path}'
        data = {
            "message": commit_message,
            "content": base64.b64encode(new_content.encode('utf-8')).decode('utf-8'),
            "branch": self.branch,
            "sha": sha
        }
        response = requests.put(url, json=data, headers=self.headers)
        if response.status_code == 200:
            print(f"File {file_path} successfully updated.")
        else:
            print(f"Error updating file: {response.status_code} - {response.text}")
            self.error_found = True

    def rollback_file(self, file_path):
        """Rolls back the specified file to its previous version."""
        # Get the previous commit SHA for the file
        previous_commit_sha = self.get_previous_commit_sha_for_file(file_path)
        if previous_commit_sha is None:
            print("No previous version found or error occurred.")
            return

        # Get the file contents from the previous commit
        previous_content, _ = self.get_file_contents(file_path, previous_commit_sha)
        if previous_content is None:
            print("Failed to fetch the previous file content.")
            return

        # Get the current file SHA (to update it)
        _, current_sha = self.get_file_contents(file_path, self.branch)
        if current_sha is None:
            print("Failed to fetch the current file info.")
            return

        # Update the file with the previous content
        commit_message = f"Rollback {file_path} to previous version"
        self.update_file_contents(file_path, previous_content, commit_message, current_sha)

def main():
    GITHUB_TOKEN = 'your_github_token'
    ORGANIZATION = 'your_organization'
    REPO_NAME = 'your_repo_name'
    BRANCH = 'main'
    ENTERPRISE_DOMAIN = 'your_enterprise_domain'
    FILE_PATH = 'path/to/your/file'  # Specify the file to rollback

    reverter = GitHubReverter(GITHUB_TOKEN, ORGANIZATION, REPO_NAME, BRANCH, ENTERPRISE_DOMAIN)
    reverter.rollback_file(FILE_PATH)

    if reverter.error_found:
        sys.exit(1)

if __name__ == "__main__":
    main()