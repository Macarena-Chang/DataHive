from transformers import T5Tokenizer, T5ForConditionalGeneration, pipeline
from summarizer import Summarizer
import gradio as gr
import json 

text = '''
Using the Mouse
We can perform many Midnight Commander operations using the mouse. A directory
panel item can be selected by clicking on it and a directory can be opened by double
clicking. Likewise, the function key labels and menu bar items can be activated by
clicking on them. What is not so apparent is that the directory history can be accessed and
traversed. At the top of each directory panel there are small arrows (circled in the image
below). Clicking on them will show the directory history (the up arrow) and move
forward and backward through the history list (the right and left arrows).
There is also an arrow to the extreme lower right edge of the command line which reveals
the command line history
'''

# from transformers import T5Tokenizer, T5ForConditionalGeneration, pipeline

""" def summarize(text):
    model = Summarizer()
    response = model(text)
    return response """




def summarize(text):
    model_name = "t5-small"
    tokenizer = T5Tokenizer.from_pretrained(model_name)
    model = T5ForConditionalGeneration.from_pretrained(model_name)
    summarizer = pipeline("summarization", model=model, tokenizer=tokenizer)
    summary = summarizer(text, max_length=2000, min_length=50, do_sample=False)
    print(summary[0]['summary_text'])
    return summary[0]['summary_text']
