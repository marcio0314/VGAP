from celery import shared_task
import subprocess
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

@shared_task(bind=True, name="vgap.tasks.maintenance.prune_docker")
def prune_docker_resources(self, deep: bool = False) -> Dict[str, Any]:
    """
    Prunes Docker resources (images, containers, networks, cache).
    Requires Docker socket mounted and Docker CLI installed.
    """
    logger.info(f"Starting Docker prune task (deep={deep})")
    
    results = {
        "images_deleted": [],
        "space_reclaimed": 0,
        "output": "",
        "success": False
    }

    try:
        # 1. Prune System (Containers, Networks, Images)
        # -a: Prune all unused images not just dangling ones
        # -f: Force
        # --volumes: Prune volumes (Use with caution!)
        
        cmd = ["docker", "system", "prune", "-f"]
        if deep:
            cmd.append("-a") # All unused images
            # We explicitly do NOT add --volumes to keep data safe unless specifically requested
            # But the requirement was "unused volumes"
            # We can run a separate volume prune command
        
        # Prune request
        proc = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True
        )
        results["output"] += proc.stdout
        
        # Parse output for space reclaimed is hard with raw output, but we can capture it.
        # "Total reclaimed space: 1.2GB"
        
        # 2. Prune Volumes (if deep)
        if deep:
            # Dangerous, proceed with care. User requested "unused volumes"
            # "docker volume prune -f"
             proc_vol = subprocess.run(
                ["docker", "volume", "prune", "-f"],
                capture_output=True,
                text=True,
                check=False
            )
             results["output"] += "\n" + proc_vol.stdout

        results["success"] = True
        logger.info("Docker prune completed successfully")
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Docker prune failed: {e.stderr}")
        results["error"] = e.stderr
        results["success"] = False
    except Exception as e:
        logger.exception("Unexpected error during docker prune")
        results["error"] = str(e)
        results["success"] = False

    return results

@shared_task(bind=True, name="vgap.tasks.maintenance.scan_docker")
def scan_docker_usage(self) -> Dict[str, Any]:
    """
    Returns Docker disk usage info using 'docker system df --format json'.
    """
    try:
        proc = subprocess.run(
            ["docker", "system", "df", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            check=True
        )
        # Docker output might be multiple JSON objects separated by newlines
        # We need to parse them.
        output = proc.stdout.strip().split('\n')
        parsed = [json.loads(line) for line in output if line]
        
        return {"usage": parsed, "success": True}
    except Exception as e:
        return {"error": str(e), "success": False}
