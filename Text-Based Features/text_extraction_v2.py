import replicate
import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
import json

def youtube_setup():
    load_dotenv()
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    youtube = build("youtube", "v3", developerKey = youtube_api_key)

    return youtube
youtube = youtube_setup()


# load imgs from file for analysis
def load_images(folder):
    imgs = []
    files = os.listdir(folder)

    for file in files:
        full_path = os.path.join(folder, file)

        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            imgs.append(full_path)
    
    return imgs

def get_text(image_paths):
    input = {
        "prompt": ("For each furniture manual step, give a textual description of the procedure and objects. Each textual description should be 3-5 sentences. Rules: \n" 
                    "If parts are labeled, refer to them with that label. Otherwise, infer what the part is.\n The output should ONLY include a textual description for each step, in JSON format, ie. STEP 1: Description."),
        "system_prompt": "You are an expert in furnature assembly manuals.",
        "image_input":[open(image_path,"rb") for image_path in image_paths]
    }

    output = "".join(replicate.run("openai/gpt-4o", input))
    # print("Text Description:\n",output,'\n\n\n')
    return output

def get_tools(image_paths, tool_list = []):
    input = {
        "prompt": ("For each furniture manual step, give a list of tool(s) needed to complete the step. If a tool is explicitely labeled and shown, include it in the list. Otherwise, infer from each step what tools (if any) are required. Include only TOOLS, not PARTS. Output should ONLY be a JSON formatted string, ie. STEP 1: tool(s)"),
        "system_prompt": "You are an expert in furnature assembly manuals.",
        "image_input":[open(image_path,"rb") for image_path in image_paths]
    }

    output = "".join(replicate.run("openai/gpt-4o", input))
    # print("Tools:\n",output,'\n\n\n')
    return output

def get_checklist(image_paths):
    description = get_text(image_paths)

    prompt = f"From this JSON file with textual descriptions of furniture assembly manual steps, create a checklist of actions to follow for each step. Checklists should only include actions shown in the individual diagram. The output should ONLY include a checklist for each step, in JSON format. Assembly manual pages are also attached for context.  \n\nTextual descriptions in JSON format: {description}"
    
    input = {
        "prompt": prompt,
        "system_prompt": "You are an expert in furniture assembly manuals.",
        "image_input":[open(image_path,"rb") for image_path in image_paths]
    }

    output = "".join(replicate.run("openai/gpt-4o", input))
    # print(f"Checklist: {output}")
    return output

def get_youtube_search(image_path):
    description = get_text(image_path)

    prompt = f"From this textual description of a furniture assembly step, identify one simple Youtube search that will assist a customer completing this assembly step. ONLY RETURN THE TEXT FOR THE YOUTUBE SEARCH. KEEP TEXT UNDER 6 WORDS. I've also attached the manual page for reference. \n\n Textual Description: {description}"
    
    input = {
        "prompt": prompt,
        "system_prompt": "You are an expert in furnature assembly manuals and constructing Youtube searches.",
        "image_input":[open(image_path,"rb")]
    }
    
    search_query = "".join(replicate.run("openai/gpt-4o", input))
    
    print(f"Youtube Search: {search_query}\n\n")
    return search_query

def get_youtube_urls(image_path):
    search_query = get_youtube_search(image_path)

    request = youtube.search().list(
        q=search_query,
        part = "snippet",
        type = "video",
        maxResults = 3
    ).execute()

    video_urls = []

    print("Videos:\n\n")
    for item in request["items"]:
        print(item["snippet"], "\n\n")
        video_urls.append(item["snippet"])
    
    return video_urls

def clean_JSON_string(text):
    lines = text.splitlines()
    lines = lines[1:len(lines)-1]
    text = "".join(lines)

    print(text,'\n\n')

    return text

images = load_images("../pdfs/shelf_2")
checklists = clean_JSON_string(get_checklist(images))
tools = clean_JSON_string(get_tools(images))

checklists_json = json.loads(checklists)
tools_json = json.loads(tools)

# print(json.dumps(checklists,indent=4))
# print(json.dumps(tools, indent = 4))