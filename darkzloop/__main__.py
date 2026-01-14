import sys
from darkzloop.cli.main import app

# For simpler UX: darkzloop "task" should work like darkzloop run "task"
if __name__ == "__main__":
    args = sys.argv[1:]
    known_commands = ["run", "batch", "doctor", "--help", "-h", "--version"]
    
    if args and args[0] not in known_commands and not args[0].startswith("-"):
        # Insert "run" before the task
        sys.argv.insert(1, "run")
    
    app()
