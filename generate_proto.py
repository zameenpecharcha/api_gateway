import os
import subprocess
import sys

def generate_proto_for_service(service_name, proto_dir, proto_file):
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
        
    except subprocess.CalledProcessError as e:
        print(f"Error generating {service_name} proto files: {str(e)}")

def generate_proto():
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Auth service protos
    auth_proto_dir = os.path.join(current_dir, "app", "proto_files", "auth")
    auth_proto_file = os.path.join(auth_proto_dir, "auth.proto")
    generate_proto_for_service("auth", auth_proto_dir, auth_proto_file)
    
    # User service protos
    user_proto_dir = os.path.join(current_dir, "app", "proto_files", "user")
    user_proto_file = os.path.join(user_proto_dir, "user.proto")
    generate_proto_for_service("user", user_proto_dir, user_proto_file)

    # Posts service protos
    posts_proto_dir = os.path.join(current_dir, "app", "proto_files", "posts")
    posts_proto_file = os.path.join(posts_proto_dir, "post.proto")
    generate_proto_for_service("post", posts_proto_dir, posts_proto_file)

    # Property service protos
    property_proto_dir = os.path.join(current_dir, "app", "proto_files", "property")
    property_proto_file = os.path.join(property_proto_dir, "property.proto")
    generate_proto_for_service("property", property_proto_dir, property_proto_file)

    # Comments service protos
    comments_proto_dir = os.path.join(current_dir, "app", "proto_files", "comments")
    comments_proto_file = os.path.join(comments_proto_dir, "comments.proto")
    generate_proto_for_service("comments", comments_proto_dir, comments_proto_file)

if __name__ == "__main__":
    generate_proto() 