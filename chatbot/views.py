from django.shortcuts import render

import requests
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponse
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, PostbackEvent, TextMessage, TextSendMessage, ImageSendMessage, FlexSendMessage
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from django.core.paginator import Paginator
from django.shortcuts import render
import json
from .models import *

from pathlib import Path
import os
from django.core.paginator import Paginator
from django.shortcuts import render
from datetime import datetime

parser = WebhookHandler(settings.LINE_CHANNEL_SECRET)
line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)

BASE_DIR = Path(__file__).resolve().parent.parent

def send_loading_animation(user_id):
    url = "https://api.line.me/v2/bot/chat/loading/start"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.LINE_CHANNEL_ACCESS_TOKEN}",
    }
    data = {
        "chatId": user_id,
        "loadingSeconds": 5  # 你可以修改這個秒數
    }

    # 發送 POST 請求到 LINE API
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code == 202:
        print("Loading animation sent successfully")
    else:
        print(f"Error: {response.status_code}, {response.text}")
        
def course_feedback(request):
    query = request.GET.get('query', '')  # 取得搜尋參數

    # 如果有搜尋條件，根據課名或老師過濾
    if query:
        all_feedback = Course.objects.filter(course_name__icontains=query) | Course.objects.filter(teacher_name__icontains=query)
    else:
        all_feedback = Course.objects.all().order_by('-last_updated_time')

    # 使用 Paginator 進行分頁，每頁顯示 10 則評價
    paginator = Paginator(all_feedback, 10)
    page_number = request.GET.get('page')
    feedback = paginator.get_page(page_number)

    context = {
        'feedback': feedback,
    }
    return render(request, 'course_feedback.html', context)

def dynamic_flex_message_package(title_name, candidate_list, label_type):
    # 引入 JSON 檔案
    json_path = os.path.join(BASE_DIR, 'chatbot', 'reply_course_teacher_list.json')
    flex = json.load(open(json_path, 'r', encoding='utf-8'))    

    # 設定標題為傳入的名稱 (可以是老師名或課程名)
    flex['body']['contents'][0]['text'] = f"哪位老師的{title_name}?" if label_type == 'teacher' else f"{title_name}老師的哪堂課?"

    # 設定顏色列表
    colors = ['#F0C29E', '#A1DE95', '#F5C578', '#91D9C2', '#DFC493', 
              '#F0C29E', '#A1DE95', '#F5C578', '#91D9C2', '#DFC493']

    # 根據傳入的 candidate_list 動態生成按鈕
    for i, name in enumerate(candidate_list, start=1):
        button = {
            'type': 'box',
            'layout': 'vertical',
            'spacing': 'none',
            'contents': [{
                'type': 'button',
                'style': 'secondary',
                'action': {
                    'type': 'postback',
                    'label': name,
                    # 注意這裡的 data 格式，根據傳入的參數動態生成資料
                    'data': f"{name}-{title_name}" if label_type == "teacher" else f"{title_name}-{name}" 
                },
                'color': "#FFFFFF",
                'margin': 'xs',
                'offsetTop': 'none',
                'height': 'sm'
            }],
            'flex': 0,
            'borderWidth': 'medium',
            'cornerRadius': 'xxl',
            'offsetTop': 'none',
            'margin': 'md',
            'backgroundColor': "#FFFFFF"
        }
        flex['body']['contents'].append(button)
    return flex

def flex_message_package(course_info):
    json_path = os.path.join(BASE_DIR, 'chatbot', 'reply_evaluation.json')
    flex = json.load(open(json_path, 'r', encoding='utf-8'))

    flex['header']['contents'][0]['text'] = course_info['course_name']
    flex['header']['contents'][1]['text'] = course_info['teacher_name']
    flex['body']['contents'][0]['contents'][0]['contents'][0]['text'] = course_info['feedback_content']
    flex['body']['contents'][0]['contents'][2]['contents'][1]['text'] = course_info['course_type']
    flex['body']['contents'][0]['contents'][3]['contents'][1]['text'] = course_info['evaluation_semester']
    flex['body']['contents'][0]['contents'][4]['contents'][1]['text'] = course_info['submitter_name']
    flex['footer']['contents'][0]['contents'][0]['text'] = f"{course_info['teacher_name']}-{course_info['course_name']}"
    flex['footer']['contents'][0]['contents'][1]['text'] = f"第{course_info['number']}則"
    flex['footer']['contents'][1]['contents'][0]['contents'][0]['action']['uri'] = "https://google.com"
    flex['footer']['contents'][1]['contents'][1]['contents'][0]['action']['uri'] = "https://google.com"
    flex['footer']['contents'][1]['contents'][2]['contents'][0]['action']['text'] = f"{course_info['teacher_name']}-{course_info['course_name']}"
    

    return flex

def get_line_display_name(user_id):
    try:
        profile = line_bot_api.get_profile(user_id)
        display_name = profile.display_name
        print(type(profile))
        return display_name
    except LineBotApiError as e:
        print(f"Error fetching user profile: {e}")
        return "匿名"

def get_user_info(user_id):
    try:
        user_info = UserInfo.objects.get(user_id=user_id)
        return user_info
    except UserInfo.DoesNotExist:
        return None
    
def register_user_info(user_id, display_name):
    user_info, created = UserInfo.objects.get_or_create(
        user_id=user_id, 
        defaults={'display_name': display_name})
    if not created:
        user_info.display_name = display_name
        user_info.save()

def send_custom_rich_menu(user_info):
    # 處理判斷使用者現在年級
    # 西元轉民國
    current_year = datetime.now().year - 1911
    user_year = int(user_info.year)
    # 使用者不是大一，就變更圖文選單
    # 如 118 級同學在民國 115 年是大二生
    # 118 - 115 = 3，不是 4 就變更圖文選單
    if current_year - user_year != 4:
        if line_bot_api.get_rich_menu_id_of_user(user_info.user_id) != settings.CUSTOM_RICH_MENU_ID:
            line_bot_api.link_rich_menu_to_user(
                user_info.user_id, 
                settings.CUSTOM_RICH_MENU_ID)

@csrf_exempt
def callback(request):
    # 確認請求是來自 LINE 的 webhook
    signature = request.META['HTTP_X_LINE_SIGNATURE']

    # 取得 request body
    body = request.body.decode('utf-8')

    try:
        # 驗證來自 LINE 的簽名
        parser.handle(body, signature)
    except InvalidSignatureError:
        return HttpResponseForbidden()
    except LineBotApiError:
        return HttpResponseForbidden()

    return HttpResponse('OK')

# 處理訊息的事件
@parser.add(MessageEvent, message=TextMessage)
def handle_msg(event):    
    user_message = event.message.text  # 取得使用者發送的文字
    user_id = event.source.user_id
    if get_user_info(user_id) is None:
        flex_message = json.load(open(os.path.join(BASE_DIR, 'chatbot', 'reply_year_option.json'), 'r', encoding='utf-8'))
        message = FlexSendMessage(
                            alt_text=f"請選擇系級",
                            contents=flex_message
                        )
        line_bot_api.reply_message(
                    event.reply_token,
                    message)
        return
    # 使用者已回答年級問題，判斷是否為大一生
    else:
        user_info = get_user_info(user_id)
        send_custom_rich_menu(user_info)
    filtered_teacher = Course.objects.filter(teacher_name=user_message)
    filtered_course = Course.objects.filter(course_name=user_message)
    filtered_course_alias = CourseAlias.objects.filter(alias=user_message)
    
    if filtered_teacher.exists():
        send_loading_animation(user_id)
        
        teacher_name = user_message
        #values_list 是以陣列裝課程名稱
        #distinct 可以把可能重複的老師名做過濾
        candidate_courses = filtered_teacher.values_list(
        'course_name', flat=True).distinct()
        #稍後會製作這個漂亮的函式，先呼叫它
        flex_message = dynamic_flex_message_package(
        teacher_name, candidate_courses, label_type='course' )

        message = FlexSendMessage(
                            alt_text=f"{teacher_name} 老師的課程",
                            contents=flex_message
                        )
        print(flex_message)
        line_bot_api.reply_message(
                    event.reply_token,
                    message)
        
    elif filtered_course.exists():
        send_loading_animation(user_id)
        
        course_name = user_message
        #values_list 是以陣列裝課程名稱
        #distinct 可以把可能重複的老師名做過濾
        candidate_teachers = filtered_course.values_list(
        'teacher_name', flat=True).distinct()
        #稍後會製作這個漂亮的函式，先呼叫它
        flex_message = dynamic_flex_message_package(
        course_name, candidate_teachers, label_type='teacher')

        message = FlexSendMessage(
                            alt_text=f"{course_name} 的老師",
                            contents=flex_message
                        )
        line_bot_api.reply_message(
                    event.reply_token,
                    message)    
        
    elif filtered_course_alias.exists():
        send_loading_animation(user_id)
        
        # 提取所有對應的課程名稱，這裡假設只需要第一個課程名稱
        full_course_name = filtered_course_alias.values_list('course_name', flat=True).first()

        # 根據課程名稱查詢對應的老師
        filtered_course = Course.objects.filter(course_name=full_course_name).values_list(
            'teacher_name', flat=True).distinct()

        # 將查詢結果轉換為候選老師列表
        candidate_teachers = list(filtered_course)

        # 呼叫動態生成訊息的函式，顯示老師的選擇
        flex_message = dynamic_flex_message_package(
            full_course_name, candidate_teachers, label_type='teacher')

        message = FlexSendMessage(
            alt_text=f"{full_course_name} 的老師",
            contents=flex_message
        )

        # 回覆訊息給使用者
        line_bot_api.reply_message(
            event.reply_token,
            message
        )
        
    else:    
        print("Empty")   

@parser.add(PostbackEvent)
def handle_postback(event):
    #取得使用者點按鈕時回傳的資料
    postback_data = event.postback.data
    user_id = event.source.user_id
    send_loading_animation(user_id)
    
    #還記得前面提及按鈕背後的資料嗎? 在這!
    #postback_data 格式為 "課程名稱-老師名稱"
    if "-" in postback_data:
        teacher_name = postback_data.split("-")[0]
        course_name = postback_data.split("-")[1]

        filtered_courses = Course.objects.filter(
            teacher_name=teacher_name, course_name=course_name)[:5]
        if filtered_courses.exists():
            messages = []

            # 使用 enumerate 給每個課程加上編號
            for idx, course in enumerate(filtered_courses, start=1):  

                # 準備課程資料以傳入 flex_message_package 函式
                course_info = {
                    'course_name': course.course_name,
                    'teacher_name': course.teacher_name,
                    'course_type': course.course_type,
                    'feedback_content': course.feedback_content,
                    'evaluation_semester': course.evaluation_semester,
                    'submitter_name': course.submitter_name,
                    'number': str(idx),  # 這裡的 idx 是第幾則的意思
                    }

                # 呼叫 flex_message_package 函式來產生 Flex Message
                flex_message = flex_message_package(course_info)

                # 使用 FlexSendMessage 回傳 Flex Message
                messages.append(FlexSendMessage(
                        alt_text=f"課程評價：{course.course_name}",
                        contents=flex_message
                    ))

            line_bot_api.reply_message(
                event.reply_token,
                messages  # 回傳 Flex Message 列表
            )         
        else:
            print("Empty")
    elif "year_" in postback_data:
        year = postback_data.split("_")[1]
        display_name = get_line_display_name(user_id)
        register_user_info(user_id, display_name)
        user_info = get_user_info(user_id)
        user_info.year = year
        user_info.save()
        message = TextSendMessage(text=f"嗨！{year}級的同學，現在可以開始搜尋課程或老師了！或是查看圖文選單可以查看更多規則~")
        line_bot_api.reply_message(
            event.reply_token,
            message
        )
    else:
        print("Empty")