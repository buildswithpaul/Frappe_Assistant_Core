# -*- coding: utf-8 -*-
# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Secure User Context Management for Frappe Assistant
Provides utilities for managing user context during code execution
"""

import frappe
import copy
from contextlib import contextmanager
from typing import Optional, Dict, Any


@contextmanager
def secure_user_context(username: Optional[str] = None, require_system_manager: bool = True):
    """
    Context manager for secure user context management during code execution
    
    This context manager:
    1. Saves the current user context and session state
    2. Optionally switches to a different user context
    3. Validates permissions (System Manager required by default)
    4. Ensures proper context restoration even if exceptions occur
    5. Maintains audit trail of who executed code
    
    Args:
        username (str, optional): Username to switch context to. If None, uses current user
        require_system_manager (bool): Whether System Manager role is required (default: True)
    
    Yields:
        str: The username under which code will execute
        
    Raises:
        frappe.PermissionError: If user lacks required permissions
        frappe.DoesNotExistError: If username doesn't exist
    """
    # Save current state for restoration
    original_user = frappe.session.user
    original_session_data = copy.deepcopy(getattr(frappe.local.session, 'data', {}))
    original_user_perms = copy.deepcopy(getattr(frappe.local, 'user_perms', {}))
    original_role_permissions = copy.deepcopy(getattr(frappe.local, 'role_permissions', {}))
    
    # Track if we changed user context
    context_changed = False
    
    try:
        # Determine target user
        target_user = username or original_user
        
        # Validate target user exists
        if target_user != "Administrator" and not frappe.db.exists("User", target_user):
            raise frappe.DoesNotExistError(f"User '{target_user}' does not exist")
        
        # Switch user context if different from current
        if target_user != original_user:
            frappe.set_user(target_user)
            context_changed = True
        
        # Get current user after potential context switch
        current_user = frappe.session.user
        
        # Validate permissions
        if require_system_manager:
            user_roles = frappe.get_roles(current_user)
            if "System Manager" not in user_roles:
                raise frappe.PermissionError(
                    f"🚫 Security: User '{current_user}' lacks System Manager role required for code execution. "
                    f"Current roles: {', '.join(user_roles)}"
                )
        
        # Additional security validation
        user_doc = frappe.get_doc("User", current_user)
        if not user_doc.enabled:
            raise frappe.PermissionError(f"🚫 Security: User '{current_user}' is disabled")
        
        # Log context switch for audit trail
        if context_changed:
            frappe.logger().info(
                f"User context switched: {original_user} -> {current_user} for code execution"
            )
        
        # Yield control with the validated user context
        yield current_user
        
    except Exception as e:
        # Log security-related errors for audit
        frappe.logger().error(
            f"Secure user context error - Original: {original_user}, Target: {username}, Error: {str(e)}"
        )
        raise
        
    finally:
        # Always restore original context, even if exceptions occur
        try:
            if context_changed and original_user:
                # Restore user context
                frappe.local.session.user = original_user
                frappe.local.session.data = original_session_data
                frappe.local.user_perms = original_user_perms
                frappe.local.role_permissions = original_role_permissions
                
                # Clear any cached permissions for the temporary user
                frappe.clear_cache(user=target_user)
                
                frappe.logger().info(f"User context restored: {target_user} -> {original_user}")
                
        except Exception as restore_error:
            # Log restoration errors but don't re-raise to avoid masking original errors
            frappe.logger().error(f"Failed to restore user context: {str(restore_error)}")


def validate_user_permissions(username: str, required_roles: list = None) -> Dict[str, Any]:
    """
    Validate user permissions and return detailed permission information
    
    Args:
        username (str): Username to validate
        required_roles (list, optional): List of required roles
    
    Returns:
        dict: Permission validation results
    """
    if required_roles is None:
        required_roles = ["System Manager"]
    
    try:
        # Check if user exists
        if not frappe.db.exists("User", username):
            return {
                "valid": False,
                "error": f"User '{username}' does not exist",
                "user_roles": [],
                "missing_roles": required_roles
            }
        
        # Get user document
        user_doc = frappe.get_doc("User", username)
        
        # Check if user is enabled
        if not user_doc.enabled:
            return {
                "valid": False,
                "error": f"User '{username}' is disabled",
                "user_roles": [],
                "missing_roles": required_roles
            }
        
        # Get user roles
        user_roles = frappe.get_roles(username)
        
        # Check required roles
        missing_roles = [role for role in required_roles if role not in user_roles]
        
        return {
            "valid": len(missing_roles) == 0,
            "error": f"Missing required roles: {', '.join(missing_roles)}" if missing_roles else None,
            "user_roles": user_roles,
            "missing_roles": missing_roles,
            "user_enabled": user_doc.enabled,
            "user_email": user_doc.email
        }
        
    except Exception as e:
        return {
            "valid": False,
            "error": f"Permission validation failed: {str(e)}",
            "user_roles": [],
            "missing_roles": required_roles
        }


def get_execution_user_info(username: str = None) -> Dict[str, Any]:
    """
    Get comprehensive user information for code execution context
    
    Args:
        username (str, optional): Username to get info for (defaults to current user)
    
    Returns:
        dict: User information including roles, permissions, and context
    """
    target_user = username or frappe.session.user
    
    try:
        # Get basic user info
        user_doc = frappe.get_doc("User", target_user)
        user_roles = frappe.get_roles(target_user)
        
        # Check System Manager access
        has_system_manager = "System Manager" in user_roles
        
        # Get permission summary
        permission_info = validate_user_permissions(target_user)
        
        return {
            "username": target_user,
            "email": user_doc.email,
            "full_name": user_doc.full_name or target_user,
            "enabled": user_doc.enabled,
            "roles": user_roles,
            "has_system_manager": has_system_manager,
            "can_execute_code": permission_info["valid"],
            "permission_errors": permission_info.get("error"),
            "session_user": frappe.session.user,
            "is_current_user": target_user == frappe.session.user
        }
        
    except Exception as e:
        return {
            "username": target_user,
            "error": f"Failed to get user info: {str(e)}",
            "can_execute_code": False,
            "session_user": frappe.session.user,
            "is_current_user": target_user == frappe.session.user
        }


@contextmanager
def audit_code_execution(code_snippet: str = "", user_context: str = None):
    """
    Context manager for auditing code execution with user context
    
    Args:
        code_snippet (str): Code being executed (for audit trail)
        user_context (str): User under which code executes
    
    Yields:
        dict: Execution tracking information
    """
    execution_id = frappe.generate_hash(length=8)
    start_time = frappe.utils.now()
    
    # Log execution start
    audit_info = {
        "execution_id": execution_id,
        "user": user_context or frappe.session.user,
        "start_time": start_time,
        "code_length": len(code_snippet),
        "code_preview": code_snippet[:200] + "..." if len(code_snippet) > 200 else code_snippet
    }
    
    frappe.logger().info(f"Code execution started - ID: {execution_id}, User: {audit_info['user']}")
    
    try:
        yield audit_info
        
        # Log successful completion
        end_time = frappe.utils.now()
        duration = frappe.utils.time_diff_in_seconds(end_time, start_time)
        
        frappe.logger().info(
            f"Code execution completed - ID: {execution_id}, Duration: {duration}s, User: {audit_info['user']}"
        )
        
    except Exception as e:
        # Log execution error
        end_time = frappe.utils.now()
        duration = frappe.utils.time_diff_in_seconds(end_time, start_time)
        
        frappe.logger().error(
            f"Code execution failed - ID: {execution_id}, Duration: {duration}s, "
            f"User: {audit_info['user']}, Error: {str(e)}"
        )
        raise


def test_user_context_security():
    """Test function to verify user context management"""
    current_user = frappe.session.user
    print(f"Testing user context security for user: {current_user}")
    
    # Test current user context
    try:
        with secure_user_context() as exec_user:
            print(f"✅ Current user context: {exec_user}")
            user_info = get_execution_user_info()
            print(f"✅ User info retrieved: {user_info['full_name']} ({user_info['username']})")
    except Exception as e:
        print(f"❌ Current user context failed: {e}")
    
    # Test permission validation
    perm_info = validate_user_permissions(current_user)
    print(f"✅ Permission validation: Valid={perm_info['valid']}, Roles={perm_info['user_roles']}")
    
    print("User context security test completed.")


if __name__ == "__main__":
    # Run tests if executed directly
    test_user_context_security()