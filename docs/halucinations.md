** Qwen Halucinations **

```
-`qwen2.5:0.5b` was halucinating and not properly giving its identity.
Maybe because of its a chinese model made by alibaba and trained on 0.5b parameters.

-After making memory.json to retrieve data from previous prompts but failing to remember name.

-Maybe the halucinations are because of how the data is being stored in the json file.

-Currently the llm is reading the previous chats and give the response from them and by itself like a RAG model

```
