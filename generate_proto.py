import os
import subprocess
import sys

def generate_proto_for_service(service_name, proto_dir, proto_file):
    if not os.path.isfile(proto_file):
        print(f"Skipping {service_name}: proto file not found at {proto_file}")
        return False

    # Create __init__.py files
    os.makedirs(proto_dir, exist_ok=True)
    with open(os.path.join(proto_dir, "__init__.py"), "w") as f:
        pass
    
    # Command to generate Python code from proto file
    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"--proto_path={os.path.dirname(proto_file)}",
        f"--python_out={os.path.dirname(proto_file)}",
        f"--grpc_python_out={os.path.dirname(proto_file)}",
        proto_file
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"{service_name} proto files generated successfully!")
        
        # Fix imports in generated files
        pb2_grpc_file = os.path.join(proto_dir, f"{service_name}_pb2_grpc.py")
        with open(pb2_grpc_file, 'r') as f:
            content = f.read()
        
        # Replace the import statement
        content = content.replace(
            f'import {service_name}_pb2 as {service_name}__pb2',
            f'from . import {service_name}_pb2 as {service_name}__pb2'
        )
        
        with open(pb2_grpc_file, 'w') as f:
            f.write(content)
            
        print(f"Fixed imports in {service_name} generated files!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error generating {service_name} proto files: {str(e)}")
        return False

def generate_proto():
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    services = [
        ("auth", "auth", "auth.proto"),
        ("user", "user", "user.proto"),
        ("post", "posts", "post.proto"),
        ("property", "property", "property.proto"),
        ("comments", "comments", "comments.proto"),
    ]

    results = []
    for service_name, proto_subdir, proto_filename in services:
        proto_dir = os.path.join(current_dir, "app", "proto_files", proto_subdir)
        proto_file = os.path.join(proto_dir, proto_filename)
        results.append(generate_proto_for_service(service_name, proto_dir, proto_file))

    generated = sum(1 for ok in results if ok)
    skipped = len(results) - generated
    print(f"Done: {generated} generated, {skipped} skipped.")
    return all(results) or generated > 0

if __name__ == "__main__":
    generate_proto() 