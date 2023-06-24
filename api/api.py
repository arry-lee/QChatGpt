import requests

true = True
false = False
headers = """
Accept: application/json, text/plain, */*
Accept-Encoding: gzip, deflate, br
Accept-Language: zh-CN,zh;q=0.9,en;q=0.8
Content-Type: application/json
Origin: https://chat2.jinshutuan.com
Referer: https://chat2.jinshutuan.com/
Sec-Ch-Ua: "Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"
Sec-Ch-Ua-Mobile: ?0
Sec-Ch-Ua-Platform: "Windows"
Sec-Fetch-Dest: empty
Sec-Fetch-Mode: cors
Sec-Fetch-Site: cross-site
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36
"""
headers = dict(x.split(": ", 1) for x in headers.splitlines() if x)


def chat(prompt):
    data = {
        "prompt"        : prompt,
        "userId"        : "#/chat/1686749073469",
        "network"       : true,
        "system"        : "",
        "withoutContext": false,
        "stream"        : false
    }
    url = 'https://api.binjie.fun/api/generateStream'
    rsp = requests.post(url, json=data, headers=headers)
    answer = rsp.content.decode('utf-8')
    return answer


# while True:
#     prompt = input('>>>')
#     if prompt == 'q':
#         break
#     print(chat(prompt))
