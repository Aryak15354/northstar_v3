"""
Archive Completed Specs
Moves completed specs to archive directory.
"""
from pathlib import Path
import shutil
import logging

workspace = Path.cwd()
specs_dir = workspace / ".kiro/specs"
archive_dir = specs_dir / "archive"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Specs to keep active
ACTIVE_SPECS = {
    "system-integrity-repair",
    "v3-cleanup-organization"
}

def archive_completed_specs():
    """Move completed specs to archive"""
    archive_dir.mkdir(exist_ok=True)
    
    archived = []
    for spec_dir in specs_dir.iterdir():
        if not spec_dir.is_dir() or spec_dir.name == "archive":
            continue
        
        if spec_dir.name in ACTIVE_SPECS:
            logger.info(f"  ✓ Keeping active: {spec_dir.name}")
            continue
        
        # Check if spec has tasks.md with all tasks complete
        tasks_file = spec_dir / "tasks.md"
        if tasks_file.exists():
            content = tasks_file.read_text()
            # Simple heuristic: if it has tasks and most are marked complete
            if "- [x]" in content or "- [ ]" not in content:
                dest = archive_dir / spec_dir.name
                if dest.exists():
                    logger.warning(f"  ⚠ {spec_dir.name} already in archive, skipping")
                else:
                    shutil.move(str(spec_dir), str(dest))
                    archived.append(spec_dir.name)
                    logger.info(f"  ✓ Archived: {spec_dir.name}")
    
    return archived

def create_specs_readme():
    """Create README.md in specs directory"""
    readme_path = specs_dir / "README.md"
    
    # Get active specs
    active = [d.name for d in specs_dir.iterdir() 
              if d.is_dir() and d.name != "archive"]
    
    # Get archived specs
    archived = []
    if archive_dir.exists():
        archived = [d.name for d in archive_dir.iterdir() if d.is_dir()]
    
    content = f"""# Northstar V3 Specifications

## Active Specs

{chr(10).join(f"- **{spec}**" for spec in sorted(active))}

## Archived Specs

{chr(10).join(f"- {spec}" for spec in sorted(archived)) if archived else "None"}

## Spec Structure

Each spec contains:
- `requirements.md` - Feature requirements using EARS patterns
- `design.md` - Design document with correctness properties
- `tasks.md` - Implementation task list

## Creating a New Spec

Use Kiro's spec workflow to create a new specification:
1. Describe your feature idea
2. Review and approve requirements
3. Review and approve design
4. Review and approve tasks
5. Execute tasks incrementally
"""
    
    readme_path.write_text(content)
    logger.info(f"✓ Created {readme_path.relative_to(workspace)}")

def main():
    logger.info("=" * 60)
    logger.info("ARCHIVE COMPLETED SPECS")
    logger.info("=" * 60)
    
    logger.info("\n[1/2] Archiving completed specs...")
    archived = archive_completed_specs()
    
    logger.info("\n[2/2] Creating specs README...")
    create_specs_readme()
    
    logger.info("\n" + "=" * 60)
    logger.info("ARCHIVING COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Specs archived: {len(archived)}")
    logger.info(f"Active specs: {len(ACTIVE_SPECS)}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
