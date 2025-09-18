#!/usr/bin/env python3
"""
🚀 GitHub-Linear Integration Tool
Handles GitHub PR webhooks and creates real Linear issues for code review
"""

import requests
import json
import logging
import hmac
import hashlib
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GitHubConfig(BaseModel):
    """Configuration for GitHub integration"""
    webhook_secret: str = Field(..., description="GitHub webhook secret for verification")
    api_token: str = Field(..., description="GitHub API token for accessing PR data")
    base_url: str = Field(default="https://api.github.com", description="GitHub API endpoint")

class LinearConfig(BaseModel):
    """Configuration for Linear integration"""
    api_key: str = Field(..., description="Linear API key")
    team_id: str = Field(..., description="Linear team ID for creating issues")
    base_url: str = Field(default="https://api.linear.app/graphql", description="Linear GraphQL endpoint")

class PRReviewIssue(BaseModel):
    """Model for PR review issues"""
    title: str
    description: str
    priority: int = 0
    labels: List[str] = []
    assignee_id: Optional[str] = None

class GitHubLinearIntegrationTool(BaseTool):
    """Tool for integrating GitHub PRs with Linear issues"""
    
    name: str = "GitHub-Linear Integration"
    description: str = "Creates Linear issues from GitHub PRs and manages code review workflow"
    github_config: GitHubConfig = Field(description="GitHub configuration")
    linear_config: LinearConfig = Field(description="Linear configuration")
    
    def __init__(self, github_config: GitHubConfig, linear_config: LinearConfig):
        super().__init__()
        self.github_config = github_config
        self.linear_config = linear_config
        self.github_headers = {
            "Authorization": f"token {github_config.api_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.linear_headers = {
            "Authorization": f"Bearer {linear_config.api_key}",
            "Content-Type": "application/json"
        }
    
    def _run(self, pr_url: str, action: str = "review") -> Dict[str, Any]:
        """Process GitHub PR and create Linear issues"""
        
        try:
            # Extract PR details from URL
            pr_details = self._extract_pr_details(pr_url)
            if not pr_details:
                raise Exception("Invalid PR URL")
            
            # Get PR data from GitHub
            pr_data = self._get_pr_data(pr_details["owner"], pr_details["repo"], pr_details["pr_number"])
            
            # Analyze PR and create review issues
            review_issues = self._analyze_pr_and_create_issues(pr_data)
            
            return {
                "success": True,
                "pr_url": pr_url,
                "issues_created": len(review_issues),
                "review_issues": review_issues,
                "message": f"Created {len(review_issues)} review issues in Linear"
            }
            
        except Exception as e:
            logger.error(f"GitHub-Linear integration error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_pr_details(self, pr_url: str) -> Optional[Dict[str, str]]:
        """Extract owner, repo, and PR number from GitHub PR URL"""
        try:
            # Handle different PR URL formats
            if "github.com" in pr_url:
                parts = pr_url.split("github.com/")[1].split("/")
                if len(parts) >= 4 and parts[2] == "pull":
                    return {
                        "owner": parts[0],
                        "repo": parts[1],
                        "pr_number": parts[3]
                    }
            return None
        except Exception:
            return None
    
    def _get_pr_data(self, owner: str, repo: str, pr_number: str) -> Dict[str, Any]:
        """Get PR data from GitHub API"""
        url = f"{self.github_config.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        
        response = requests.get(url, headers=self.github_headers)
        if response.status_code != 200:
            raise Exception(f"Failed to get PR data: {response.status_code}")
        
        pr_data = response.json()
        
        # Get PR files
        files_url = f"{url}/files"
        files_response = requests.get(files_url, headers=self.github_headers)
        if files_response.status_code == 200:
            pr_data["files"] = files_response.json()
        
        # Get PR comments
        comments_url = f"{url}/comments"
        comments_response = requests.get(comments_url, headers=self.github_headers)
        if comments_response.status_code == 200:
            pr_data["comments"] = comments_response.json()
        
        return pr_data
    
    def _analyze_pr_and_create_issues(self, pr_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze PR and create appropriate Linear issues"""
        
        review_issues = []
        
        # Create main PR review issue
        main_issue = self._create_main_pr_issue(pr_data)
        review_issues.append(main_issue)
        
        # Analyze files and create specific issues
        file_issues = self._analyze_files_and_create_issues(pr_data)
        review_issues.extend(file_issues)
        
        # Create documentation issues if needed
        doc_issues = self._create_documentation_issues(pr_data)
        review_issues.extend(doc_issues)
        
        # Create testing issues if needed
        test_issues = self._create_testing_issues(pr_data)
        review_issues.extend(test_issues)
        
        return review_issues
    
    def _create_main_pr_issue(self, pr_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create main PR review issue"""
        
        title = f"🔍 Review PR: {pr_data['title']}"
        description = f"""
## PR Review Request

**Repository:** {pr_data['base']['repo']['full_name']}
**PR:** #{pr_data['number']} - {pr_data['title']}
**Author:** {pr_data['user']['login']}
**Branch:** {pr_data['head']['ref']} → {pr_data['base']['ref']}

### Description
{pr_data.get('body', 'No description provided')}

### Changes
- **Files changed:** {len(pr_data.get('files', []))}
- **Additions:** {pr_data['additions']}
- **Deletions:** {pr_data['deletions']}

### Review Tasks
- [ ] Code quality review
- [ ] Security analysis
- [ ] Performance impact assessment
- [ ] Documentation updates
- [ ] Testing coverage

**PR URL:** {pr_data['html_url']}
**Created:** {pr_data['created_at']}
        """.strip()
        
        # Create issue in Linear
        issue_data = self._create_linear_issue(title, description, priority=2)
        
        return {
            "type": "main_review",
            "title": title,
            "linear_issue_id": issue_data.get("id"),
            "linear_issue_number": issue_data.get("number")
        }
    
    def _analyze_files_and_create_issues(self, pr_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze changed files and create specific issues"""
        
        file_issues = []
        files = pr_data.get('files', [])
        
        for file_data in files:
            filename = file_data['filename']
            additions = file_data['additions']
            deletions = file_data['deletions']
            
            # Determine issue type based on file
            if self._is_code_file(filename):
                issue_type = "code_review"
                priority = 1
            elif self._is_config_file(filename):
                issue_type = "config_review"
                priority = 2
            elif self._is_documentation_file(filename):
                issue_type = "documentation_review"
                priority = 3
            else:
                continue
            
            title = f"📝 Review {filename}"
            description = f"""
## File Review: {filename}

**File:** {filename}
**Changes:** +{additions} -{deletions}
**Type:** {issue_type.replace('_', ' ').title()}

### Review Focus
- Code quality and standards
- Potential bugs or issues
- Performance implications
- Security considerations

**PR:** #{pr_data['number']} - {pr_data['title']}
**Repository:** {pr_data['base']['repo']['full_name']}
            """.strip()
            
            # Create issue in Linear
            issue_data = self._create_linear_issue(title, description, priority=priority)
            
            file_issues.append({
                "type": issue_type,
                "filename": filename,
                "title": title,
                "linear_issue_id": issue_data.get("id"),
                "linear_issue_number": issue_data.get("number")
            })
        
        return file_issues
    
    def _create_documentation_issues(self, pr_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create documentation-related issues if needed"""
        
        doc_issues = []
        
        # Check if documentation updates are needed
        if pr_data.get('body') and len(pr_data['body']) > 100:
            # PR has substantial description, might need doc updates
            title = "📚 Update Documentation"
            description = f"""
## Documentation Update Required

**PR:** #{pr_data['number']} - {pr_data['title']}

This PR includes significant changes that may require documentation updates:

### Areas to Review
- API documentation
- User guides
- README updates
- Code comments
- Architecture diagrams

**Repository:** {pr_data['base']['repo']['full_name']}
**PR URL:** {pr_data['html_url']}
            """.strip()
            
            issue_data = self._create_linear_issue(title, description, priority=3)
            
            doc_issues.append({
                "type": "documentation",
                "title": title,
                "linear_issue_id": issue_data.get("id"),
                "linear_issue_number": issue_data.get("number")
            })
        
        return doc_issues
    
    def _create_testing_issues(self, pr_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create testing-related issues if needed"""
        
        test_issues = []
        
        # Check if tests are included
        files = pr_data.get('files', [])
        test_files = [f for f in files if self._is_test_file(f['filename'])]
        
        if not test_files and len(files) > 0:
            # No test files found, create testing issue
            title = "🧪 Add Tests"
            description = f"""
## Testing Coverage Required

**PR:** #{pr_data['number']} - {pr_data['title']}

This PR includes code changes but no corresponding tests.

### Testing Requirements
- Unit tests for new functionality
- Integration tests if applicable
- Edge case coverage
- Error handling tests

**Repository:** {pr_data['base']['repo']['full_name']}
**PR URL:** {pr_data['html_url']}
            """.strip()
            
            issue_data = self._create_linear_issue(title, description, priority=2)
            
            test_issues.append({
                "type": "testing",
                "title": title,
                "linear_issue_id": issue_data.get("id"),
                "linear_issue_number": issue_data.get("number")
            })
        
        return test_issues
    
    def _create_linear_issue(self, title: str, description: str, priority: int = 0) -> Dict[str, Any]:
        """Create issue in Linear"""
        
        mutation = """
        mutation IssueCreate($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    title
                    description
                    number
                    state {
                        name
                    }
                    team {
                        name
                    }
                    priority
                    createdAt
                }
            }
        }
        """
        
        variables = {
            "input": {
                "title": title,
                "description": description,
                "teamId": self.linear_config.team_id,
                "priority": priority
            }
        }
        
        response = requests.post(
            self.linear_config.base_url,
            headers=self.linear_headers,
            json={"query": mutation, "variables": variables}
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to create Linear issue: {response.status_code}")
        
        result = response.json()
        if not result.get("data", {}).get("issueCreate", {}).get("success"):
            raise Exception("Linear issue creation failed")
        
        return result["data"]["issueCreate"]["issue"]
    
    def _is_code_file(self, filename: str) -> bool:
        """Check if file is a code file"""
        code_extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.go', '.rs', '.php']
        return any(filename.endswith(ext) for ext in code_extensions)
    
    def _is_config_file(self, filename: str) -> bool:
        """Check if file is a configuration file"""
        config_files = ['docker-compose.yml', 'Dockerfile', 'requirements.txt', 'package.json', 'config.py', 'settings.py']
        config_extensions = ['.yml', '.yaml', '.toml', '.ini', '.cfg', '.env']
        return filename in config_files or any(filename.endswith(ext) for ext in config_extensions)
    
    def _is_documentation_file(self, filename: str) -> bool:
        """Check if file is a documentation file"""
        doc_extensions = ['.md', '.rst', '.txt', '.adoc']
        return any(filename.endswith(ext) for ext in doc_extensions)
    
    def _is_test_file(self, filename: str) -> bool:
        """Check if file is a test file"""
        test_patterns = ['test_', '_test.', 'spec.', '.spec.', 'tests/']
        return any(pattern in filename for pattern in test_patterns)
    
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature"""
        try:
            expected_signature = hmac.new(
                self.github_config.webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(f"sha256={expected_signature}", signature)
        except Exception:
            return False

