"""
Wrapper for Mergin client operations used by the web interface.
"""

# Python 3.10+ compatibility fix for older libraries using collections.Callable
import collections.abc
import collections
if not hasattr(collections, 'Callable'):
    collections.Callable = collections.abc.Callable

from mergin import MerginClient, LoginError, ClientError


def validate_credentials(url: str, username: str, password: str) -> dict:
    """
    Test Mergin credentials by attempting to log in.

    Returns:
        dict with 'success' boolean and 'message' or 'error' string
    """
    try:
        mc = MerginClient(url, login=username, password=password)
        user_info = mc.user_info()
        return {
            "success": True,
            "message": f"Successfully authenticated as {user_info.get('username', username)}",
            "user": user_info
        }
    except LoginError as e:
        return {
            "success": False,
            "error": f"Login failed: {str(e)}"
        }
    except ClientError as e:
        return {
            "success": False,
            "error": f"Connection error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def list_projects(url: str, username: str, password: str) -> dict:
    """
    List all projects accessible to the user.

    Returns:
        dict with 'success' boolean and 'projects' list or 'error' string
    """
    try:
        mc = MerginClient(url, login=username, password=password)
        projects = mc.projects_list(flag="created")
        project_list = [
            {
                "name": p["name"],
                "namespace": p["namespace"],
                "full_name": f"{p['namespace']}/{p['name']}",
                "version": p.get("version", "v0")
            }
            for p in projects
        ]
        return {
            "success": True,
            "projects": project_list
        }
    except LoginError as e:
        return {
            "success": False,
            "error": f"Login failed: {str(e)}"
        }
    except ClientError as e:
        return {
            "success": False,
            "error": f"Client error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


def list_gpkg_files(url: str, username: str, password: str, project_full_name: str) -> dict:
    """
    List all GeoPackage files in a project.

    Args:
        url: Mergin server URL
        username: Mergin username
        password: Mergin password
        project_full_name: Full project name (namespace/project)

    Returns:
        dict with 'success' boolean and 'files' list or 'error' string
    """
    try:
        mc = MerginClient(url, login=username, password=password)
        project_info = mc.project_info(project_full_name)

        gpkg_files = []
        for f in project_info.get("files", []):
            path = f.get("path", "")
            if path.lower().endswith(".gpkg"):
                gpkg_files.append({
                    "path": path,
                    "size": f.get("size", 0)
                })

        return {
            "success": True,
            "files": gpkg_files,
            "project": project_full_name
        }
    except LoginError as e:
        return {
            "success": False,
            "error": f"Login failed: {str(e)}"
        }
    except ClientError as e:
        return {
            "success": False,
            "error": f"Client error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }
