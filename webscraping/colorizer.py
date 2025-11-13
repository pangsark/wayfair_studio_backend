from dotenv import load_dotenv
import os
import replicate
from config import REPLICATE_MODEL

load_dotenv()

# file paths
colored_image = "/Users/aaronzhang/Desktop/Wayfair_Clinic/webscraping/colored_drawer.png"
diagram = "/Users/aaronzhang/Desktop/Wayfair_Clinic/webscraping/drawer_diagram.png"

def colorize_diagram(colored_image_path, diagram_path, prompt=None):
    """
    Colorized Wayfair product diagram based on reference diagram image.
    Returns output of colorized image
    """
    if prompt is None:
        prompt = ("Colorize the product dimensions diagram to be the same color as the real furniture. Only colorize the diagram, keeping the lines, arrows, and numbers.")

    with open(colored_image_path, "rb") as img1, open(diagram_path, "rb") as img2:
        input = {
            "prompt": prompt,
            "image_input": [img1, img2]
        }
        
        print(f"Running model {REPLICATE_MODEL}...")
        output = replicate.run("google/nano-banana", input=input)

        return output

# access file URL
# print(output.url())

# write to disk
# with open("output.jpg", "wb") as file:
#     file.write(output.read())

