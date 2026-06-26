


import ollama

# using Ollama model for development 
# can integrate more sophisticated reasoning models when finalising PoC 

response = ollama.chat(model='llama3:8b', messages=[
    {'role':'user', 'content':'why is the sky blue?'},
])
print(response['message']['content'])
