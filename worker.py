from openai_api_mgr import OpenAI_API_Manager
from openai import AsyncOpenAI, BadRequestError
from openai.types.responses import Response, ResponseComputerToolCall
from openai.types.responses.response_computer_tool_call import Action
from screeninfo import get_monitors
from PIL import Image
import pyscreenshot
import pyautogui
import time
import io
import asyncio
import base64
import traceback


pyautogui.FAILSAFE = False


display = get_monitors()[0]
openai_mgr = OpenAI_API_Manager()


async def screenshot() -> str:
    scr: Image = pyscreenshot.grab()
    blob = io.BytesIO()
    scr.save(blob, format='PNG')
    blob.seek(0)

    return f'data:image/png;base64,{base64.b64encode(blob.read()).decode('utf-8')}'
    



async def handle_model_action(ct_call: ResponseComputerToolCall):
    action = ct_call.action
    action_type = action.type
    
    try:
        match action_type:
            case 'click':
                x, y = action.x, action.y
                button = action.button
                print(f'Action: click at ({x}, {y}) with button "{button}"')
                # Not handling things like middle click, etc.
                if not button in ['left', 'right', 'wheel']:
                    button = 'left'

                if button == 'wheel':
                    button = 'middle'

                pyautogui.click(x, y, button=button)

            case 'double_click':
                x, y = action.x, action.y
                print(f'Action: double click at ({x}, {y})')
                pyautogui.click(x, y, button='left', clicks=2, interval=0.020)

            case 'scroll':
                x, y = action.x, action.y
                scroll_x, scroll_y = action.scroll_x, action.scroll_y
                print(f'Action: scroll at ({x}, {y}) with offsets (scroll_x={scroll_x}, scroll_y={scroll_y})')
                pyautogui.move(x, y)

                if scroll_x != 0:
                    pyautogui.click(x, y)
                    pyautogui.hscroll(scroll_x)

                if scroll_y != 0:
                    pyautogui.click(x, y)
                    pyautogui.scroll(scroll_y)
              
            case 'keypress':
                keys = action.keys
                k_lowers = [k.lower() for k in keys]

                if ('ctrl' in k_lowers) or ('shift' in k_lowers) or ('alt' in k_lowers):
                    print('Action: hotkeys: ' + ', '.join(k_lowers))
                    pyautogui.hotkey(*k_lowers)
                else:
                    for k in keys:
                        print(f'Action: keypress {k}')
                        # A simple mapping for common keys; expand as needed.
                        if k.lower() == 'enter':
                            pyautogui.press('enter')
                        elif k.lower() == 'space':
                            pyautogui.press('space')
                        else:
                            pyautogui.press(k)
            
            case 'type':
                text = action.text
                print(f'Action: type text: {text}')
                pyautogui.typewrite(text)
            
            case 'wait':
                print('Action: wait')
                await asyncio.sleep(2)

            case 'move':
                print('Action: move')
                pyautogui.move(action.x, action.y)

            case 'drag':
                print('Action: drag')
                if len(action.path) > 1:
                    path_start = action.path[0]
                    path_end = action.path[len(action.path) - 1]

                    pyautogui.move(path_start.x, path_start.y)
                    pyautogui.mouseDown(path_start.x, path_start.y)

                    await asyncio.sleep(0.1)

                    for p in action.path[1:-1]:
                        pyautogui.drag(p.x, p.y)
                        await asyncio.sleep(0.1)

                    pyautogui.mouseUp(path_end.x, path_end.y)

            case 'screenshot':
                print('Action: screenshot')

            case _:
                print(f'Unrecognized action: {action}')

    except Exception as e:
        print(f'Error handling action {action}: {e}')

    return {
        'call_id': ct_call.call_id,
        'type': 'computer_call_output',
        'output': {
            'type': 'computer_screenshot',
            'image_url': await screenshot()
        }
    }


async def computer_use_loop(response: Response, openai_api: AsyncOpenAI):
    '''
    Run the loop that executes computer actions until no 'computer_call' is found.
    '''
    while True:
        computer_calls = [item for item in response.output if item.type == 'computer_call']
        if not computer_calls:
            print('No computer call found. Output from model:')
            for item in response.output:
                print(item)
            break  # Exit when no computer calls are issued.

        tool_calls_outputs = []
            
        for computer_call in computer_calls:
            tc_out = await handle_model_action(computer_call) 
            if tc_out != None:
                tool_calls_outputs.append(tc_out)

        await asyncio.sleep(1.0)

        # Send the screenshot back as a computer_call_output
        attempts = 10
        while attempts > 0:
            try:
                response = await openai_api.responses.create(
                    model='computer-use-preview',
                    previous_response_id=response.id,
                    tools=[
                        {
                            'type': 'computer_use_preview',
                            'display_width': display.width,
                            'display_height': display.height,
                            'environment': 'windows'
                        }
                    ],
                    input = [ tool_calls_outputs[-1] ],
                    truncation='auto'
                )

                while response.status == 'in_progress':
                    await asyncio.sleep(1.5)
                    response = await openai_api.responses.retrieve(response_id=response.id)

                break
            except BadRequestError as E:
                if 'Error while downloading' in E.message:
                    attempts -= 1
                    await asyncio.sleep(2.5)
                else:
                    traceback.print_exception(E)
                    break

    return response



async def main(task: str):
    async with openai_mgr as openai_api:
        response = await openai_api.responses.create(
            model='computer-use-preview',
            tools=[{
                'type': 'computer_use_preview',
                'display_width': display.width,
                'display_height': display.height,
                'environment': 'windows'
            }],
            input=[
                {
                    'role': 'user',
                    'content': task
                }
            ],
            truncation='auto'
        )

        while response.status == 'in_progress':
            await asyncio.sleep(1.5)
            response = await openai_api.responses.retrieve(response_id=response.id)

        await computer_use_loop(response, openai_api)



print('Sleep 3 sec...')
time.sleep(3.0)
print('Starting...')

TASK = '''
You are Omega, a smart AI assistant.

Your task for today:
Find information about the Boeing-737 on Wikipedia and write down its characteristics in new google doc.

Important! You're completely autonomous, don't ask any questions in response - they won't answer you. Solve the tasks completely on your own.
Important! If you want to create a new tab in the browser, do it through the + icon at the top right of the last tab. Do not go to the start menu for this and do not launch Chrome a second time using its shortcut!!!
P.S. Scroll by wheel may not work in browser - you can drag scrollbar in this case.

'''.lstrip().rstrip()

asyncio.run(main(TASK))