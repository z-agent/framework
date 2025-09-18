#!/usr/bin/env python3
"""
🚀 REAL LINEAR TOOLS - INTEGRATED WITH VENTURE-BOT LINEAR-SERVICE
Real Linear API integration via venture-bot supabase function
No more mock data - actual Linear issues, comments, and project management
"""

import requests
import json
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LinearIssueSchema(BaseModel):
    """Schema for creating Linear issues"""
    title: str = Field(..., description="Issue title")
    description: str = Field(..., description="Issue description")
    priority: int = Field(default=2, description="Priority (0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low)")
    project_id: Optional[str] = Field(None, description="Project ID to assign issue to")

class LinearCommentSchema(BaseModel):
    """Schema for adding comments to Linear issues"""
    issue_id: str = Field(..., description="Linear issue ID")
    comment: str = Field(..., description="Comment content")

class LinearStatusSchema(BaseModel):
    """Schema for updating issue status"""
    issue_id: str = Field(..., description="Linear issue ID")
    status: str = Field(..., description="New status (e.g., 'In Progress', 'Done', 'Backlog')")

class LinearProjectSchema(BaseModel):
    """Schema for project operations"""
    project_id: str = Field(..., description="Linear project ID")

class LinearIssueDetailsSchema(BaseModel):
    """Schema for getting issue details"""
    issue_id: str = Field(..., description="Linear issue ID")

class VentureBotLinearClient:
    """Real Linear API client via venture-bot linear-service"""
    
    def __init__(self, venture_bot_url: str = None):
        # Default to local development, but can be overridden
        self.base_url = venture_bot_url or "http://localhost:54321/functions/v1/linear-service"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('SUPABASE_ANON_KEY', '')}"
        }
    
    def _make_request(self, action: str, **kwargs) -> Dict[str, Any]:
        """Make request to venture-bot linear-service"""
        try:
            payload = {"action": action, **kwargs}
            logger.info(f"🔧 Calling venture-bot linear-service: {action}")
            
            response = requests.post(
                self.base_url,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Linear service {action} successful")
                return result
            else:
                logger.error(f"❌ Linear service {action} failed: {response.status_code} - {response.text}")
                return {"error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            logger.error(f"❌ Linear service {action} error: {str(e)}")
            return {"error": f"Request failed: {str(e)}"}
    
    def create_issue(self, title: str, description: str, priority: int = 2, project_id: str = None) -> Dict[str, Any]:
        """Create a new Linear issue"""
        return self._make_request("createIssue", title=title, description=description, priority=priority, projectId=project_id)
    
    def add_comment(self, issue_id: str, comment: str) -> Dict[str, Any]:
        """Add comment to Linear issue"""
        return self._make_request("addComment", issueId=issue_id, comment=comment)
    
    def update_issue_status(self, issue_id: str, status: str) -> Dict[str, Any]:
        """Update Linear issue status"""
        return self._make_request("updateIssueStatus", issueId=issue_id, status=status)
    
    def get_issue_details(self, issue_id: str) -> Dict[str, Any]:
        """Get Linear issue details"""
        return self._make_request("getIssueDetails", issueId=issue_id)
    
    def get_project_issues(self, project_id: str) -> Dict[str, Any]:
        """Get all issues for a project"""
        return self._make_request("getProjectIssues", projectId=project_id)

class LinearScopingTool(BaseTool):
    """Real Linear scoping tool that creates actual Linear issues"""
    
    name: str = "Linear Scoping Tool"
    description: str = "Creates real Linear issues for project scoping and requirements analysis"
    args_schema: type[BaseModel] = LinearIssueSchema
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize client as instance variable, not field
        self._linear_client = VentureBotLinearClient()
    
    def _run(self, **kwargs) -> Dict[str, Any]:
        """Create a real Linear issue for scoping"""
        try:
            title = kwargs.get("title", "").strip()
            description = kwargs.get("description", "").strip()
            priority = kwargs.get("priority", 2)
            project_id = kwargs.get("project_id")
            
            if not title:
                return {"error": "Title is required for creating a Linear issue"}
            
            if not description:
                description = f"Scope analysis and requirements for: {title}"
            
            logger.info(f"🔧 Creating Linear issue: {title}")
            
            # Create real Linear issue via venture-bot
            result = self._linear_client.create_issue(
                title=title,
                description=description,
                priority=priority,
                project_id=project_id
            )
            
            if "error" in result:
                return {"success": False, "error": result["error"]}
            
            # Add initial scope analysis comment
            scope_comment = f"""
🔍 **Scope Analysis Started**

**Project**: {title}
**Priority**: {priority}
**Created**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Next Steps**:
1. Review requirements and constraints
2. Break down into actionable tasks
3. Estimate effort and timeline
4. Assign team members
5. Set milestones and deadlines

---
*Issue created by Zara Framework Linear Scoping Tool*
"""
            
            comment_result = self._linear_client.add_comment(
                issue_id=result.get("id", ""),
                comment=scope_comment
            )
            
            return {
                "success": True,
                "issue_id": result.get("id"),
                "title": title,
                "url": result.get("url"),
                "status": result.get("state", {}).get("name", "Backlog"),
                "priority": priority,
                "scope_comment_added": "error" not in comment_result,
                "message": f"✅ Linear issue created successfully: {title}"
            }
            
        except Exception as e:
            logger.error(f"❌ Linear scoping tool error: {str(e)}")
            return {"success": False, "error": f"Failed to create Linear issue: {str(e)}"}

class LinearPRReviewTool(BaseTool):
    """Real Linear PR review tool that creates actual Linear issues for PR reviews"""
    
    name: str = "Linear PR Review Tool"
    description: str = "Creates real Linear issues for GitHub PR reviews and code quality checks"
    args_schema: type[BaseModel] = LinearIssueSchema
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize client as instance variable, not field
        self._linear_client = VentureBotLinearClient()
    
    def _run(self, **kwargs) -> Dict[str, Any]:
        """Create a real Linear issue for PR review"""
        try:
            title = kwargs.get("title", "").strip()
            description = kwargs.get("description", "").strip()
            priority = kwargs.get("priority", 2)
            project_id = kwargs.get("project_id")
            
            if not title:
                return {"error": "Title is required for creating a Linear issue"}
            
            if not description:
                description = f"PR Review and code quality check for: {title}"
            
            logger.info(f"🔧 Creating Linear PR review issue: {title}")
            
            # Create real Linear issue via venture-bot
            result = self._linear_client.create_issue(
                title=f"PR Review: {title}",
                description=description,
                priority=priority,
                project_id=project_id
            )
            
            if "error" in result:
                return {"success": False, "error": result["error"]}
            
            # Add PR review checklist comment
            review_comment = f"""
🔍 **PR Review Checklist**

**PR Title**: {title}
**Priority**: {priority}
**Created**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Review Checklist**:
- [ ] Code quality and standards
- [ ] Test coverage and functionality
- [ ] Security considerations
- [ ] Performance impact
- [ ] Documentation updates
- [ ] Breaking changes review
- [ ] Accessibility compliance
- [ ] Mobile responsiveness

**Review Process**:
1. Automated checks pass
2. Code review by team member
3. Testing in staging environment
4. Final approval and merge

---
*Issue created by Zara Framework Linear PR Review Tool*
"""
            
            comment_result = self._linear_client.add_comment(
                issue_id=result.get("id", ""),
                comment=review_comment
            )
            
            return {
                "success": True,
                "issue_id": result.get("id"),
                "title": f"PR Review: {title}",
                "url": result.get("url"),
                "status": result.get("state", {}).get("name", "Backlog"),
                "priority": priority,
                "review_checklist_added": "error" not in comment_result,
                "message": f"✅ Linear PR review issue created successfully: {title}"
            }
            
        except Exception as e:
            logger.error(f"❌ Linear PR review tool error: {str(e)}")
            return {"success": False, "error": f"Failed to create Linear PR review issue: {str(e)}"}

class LinearCodingTool(BaseTool):
    """Real Linear coding tool that creates actual Linear issues for coding tasks"""
    
    name: str = "Linear Coding Tool"
    description: str = "Creates real Linear issues for coding tasks, bug fixes, and feature development"
    args_schema: type[BaseModel] = LinearIssueSchema
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize client as instance variable, not field
        self._linear_client = VentureBotLinearClient()
    
    def _run(self, **kwargs) -> Dict[str, Any]:
        """Create a real Linear issue for coding task"""
        try:
            title = kwargs.get("title", "").strip()
            description = kwargs.get("description", "").strip()
            priority = kwargs.get("priority", 2)
            project_id = kwargs.get("project_id")
            
            if not title:
                return {"error": "Title is required for creating a Linear issue"}
            
            if not description:
                description = f"Coding task implementation for: {title}"
            
            logger.info(f"🔧 Creating Linear coding issue: {title}")
            
            # Create real Linear issue via venture-bot
            result = self._linear_client.create_issue(
                title=f"Code: {title}",
                description=description,
                priority=priority,
                project_id=project_id
            )
            
            if "error" in result:
                return {"success": False, "error": result["error"]}
            
            # Add coding task template comment
            coding_comment = f"""
💻 **Coding Task Template**

**Task**: {title}
**Priority**: {priority}
**Created**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Implementation Steps**:
1. **Analysis**: Review requirements and constraints
2. **Design**: Plan architecture and data flow
3. **Development**: Write code with tests
4. **Testing**: Unit tests, integration tests
5. **Review**: Code review and quality check
6. **Deploy**: Staging and production deployment

**Acceptance Criteria**:
- [ ] Feature works as specified
- [ ] Tests pass and coverage adequate
- [ ] Code follows team standards
- [ ] Documentation updated
- [ ] No breaking changes introduced

**Estimated Effort**: TBD
**Dependencies**: None identified

---
*Issue created by Zara Framework Linear Coding Tool*
"""
            
            comment_result = self._linear_client.add_comment(
                issue_id=result.get("id", ""),
                comment=coding_comment
            )
            
            return {
                "success": True,
                "issue_id": result.get("id"),
                "title": f"Code: {title}",
                "url": result.get("url"),
                "status": result.get("state", {}).get("name", "Backlog"),
                "priority": priority,
                "coding_template_added": "error" not in comment_result,
                "message": f"✅ Linear coding issue created successfully: {title}"
            }
            
        except Exception as e:
            logger.error(f"❌ Linear coding tool error: {str(e)}")
            return {"success": False, "error": f"Failed to create Linear coding issue: {str(e)}"}

class LinearProjectManagerTool(BaseTool):
    """Real Linear project management tool for getting project information"""
    
    name: str = "Linear Project Manager"
    description: str = "Gets real Linear project information and issue details"
    args_schema: type[BaseModel] = LinearProjectSchema
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize client as instance variable, not field
        self._linear_client = VentureBotLinearClient()
    
    def _run(self, **kwargs) -> Dict[str, Any]:
        """Get Linear project information"""
        try:
            project_id = kwargs.get("project_id", "").strip()
            
            if not project_id:
                return {"error": "Project ID is required"}
            
            logger.info(f"🔧 Getting Linear project issues: {project_id}")
            
            # Get real project issues via venture-bot
            result = self._linear_client.get_project_issues(project_id=project_id)
            
            if "error" in result:
                return {"success": False, "error": result["error"]}
            
            issues = result if isinstance(result, list) else []
            
            return {
                "success": True,
                "project_id": project_id,
                "total_issues": len(issues),
                "issues": [
                    {
                        "id": issue.get("id"),
                        "title": issue.get("title"),
                        "status": issue.get("state", {}).get("name", "Unknown"),
                        "priority": issue.get("priority", 0),
                        "url": issue.get("url"),
                        "created_at": issue.get("createdAt"),
                        "updated_at": issue.get("updatedAt")
                    }
                    for issue in issues
                ],
                "message": f"✅ Retrieved {len(issues)} issues for project {project_id}"
            }
            
        except Exception as e:
            logger.error(f"❌ Linear project manager error: {str(e)}")
            return {"success": False, "error": f"Failed to get project issues: {str(e)}"}

# Export tools for auto-discovery
# Only export the variable instances, not the classes
linear_scoping_tool = LinearScopingTool()
linear_pr_review_tool = LinearPRReviewTool()
linear_coding_tool = LinearCodingTool()
linear_project_manager_tool = LinearProjectManagerTool() 