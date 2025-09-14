import os
import subprocess
import sys


def generate_proto_files():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    proto_dir = os.path.join(current_dir, "app", "proto_files", "chat")

    os.makedirs(proto_dir, exist_ok=True)

    proto_file = os.path.join(proto_dir, "chat.proto")
    if not os.path.exists(proto_file):
        print(f"Error: Proto file not found at {proto_file}")
        sys.exit(1)

    try:
        subprocess.run([
            sys.executable, "-m", "grpc_tools.protoc",
            f"--proto_path={proto_dir}",
            f"--python_out={proto_dir}",
            f"--grpc_python_out={proto_dir}",
            "chat.proto"
        ], check=True)

        # Fix import style for relative import in *_pb2_grpc.py
        pb2_grpc_file = os.path.join(proto_dir, "chat_pb2_grpc.py")
        if os.path.exists(pb2_grpc_file):
            with open(pb2_grpc_file, 'r', encoding='utf-8') as f:
                content = f.read()
            content = content.replace(
                'import chat_pb2 as chat__pb2',
                'from . import chat_pb2 as chat__pb2'
            )
            with open(pb2_grpc_file, 'w', encoding='utf-8') as f:
                f.write(content)

        print("Chat proto files generated successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error generating proto files: {e}")
        sys.exit(1)


if __name__ == "__main__":
    generate_proto_files()


