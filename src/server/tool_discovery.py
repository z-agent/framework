#!/usr/bin/env python3
"""
🔧 AUTO-TOOL DISCOVERY SYSTEM
Automatically discover and register tools from the tools directory
No more manual registration in main.py!
"""

import os
import importlib
import inspect
from typing import Dict, List, Tuple, Any
from crewai.tools import BaseTool
import logging

logger = logging.getLogger(__name__)

class ToolDiscovery:
    """Automatically discover and register tools from the tools directory"""
    
    def __init__(self, tools_dir: str = "src/tools"):
        self.tools_dir = tools_dir
        self.discovered_tools = {}
        self.registration_errors = []
    
    def discover_tools(self, tool_name: str) -> Dict[str, Tuple[BaseTool, str]]:
        """Discover all tools in the tools directory"""
        tools = {}
        
        try:
            # search using tool_search endpoint 
            # search_results = self.registry.find_tools(tool_name)
            search_results = self.registry.find_tools(tool_name)
            print(f"🔍 Search results: {search_results}")
            # get the first result
            first_result = search_results[0]
            print(f"🔍 First result: {first_result}")
            # get the tool_id
            tool_id = first_result["id"]
            print(f"🔍 Tool ID: {tool_id}")

            return search_results

        except Exception as e:
            logger.error(f"❌ Tool discovery failed: {e}")
            
        self.discovered_tools = tools
        return tools
    
    def get_registration_errors(self) -> List[str]:
        """Get list of tools that failed to register"""
        return self.registration_errors
    
    def print_discovery_summary(self):
        """Print summary of discovered tools"""
        print(f"\n🔧 TOOL DISCOVERY SUMMARY:")
        print(f"✅ Successfully discovered {len(self.discovered_tools)} tools")
        
        if self.discovered_tools:
            print(f"\n📋 Discovered Tools:")
            for tool_name, (tool_instance, source) in self.discovered_tools.items():
                description = getattr(tool_instance, 'description', 'No description')
                print(f"  🚀 {tool_name}: {description[:60]}...")
                print(f"     Source: {source}")
        
        if self.registration_errors:
            print(f"\n❌ Registration Errors ({len(self.registration_errors)}):")
            for error in self.registration_errors:
                print(f"  ⚠️  {error}")
        
        print()

# Example usage:
# discovery = ToolDiscovery()
# tools = discovery.discover_tools()
# discovery.print_discovery_summary()
