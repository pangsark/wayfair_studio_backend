
from colorizer import colorize_diagram
import os

def main():
    # file paths - TODO: make this call backend database
    colored_image = "inputs/colored_drawer.png"
    diagram = "inputs/drawer_diagram.png"
    output_path = "outputs/colorized_output.png"

    print("Starting colorization process...")
    result = colorize_diagram(colored_image, diagram)

    img_data = result.read()

    os.makedirs("outputs", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(img_data)

    print(f"Output saved to {output_path}")

if __name__ == "__main__":
    main()