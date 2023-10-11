from http import HTTPStatus
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.conf import settings

import json
import logging
import uuid

logger = logging.getLogger('frycss.views')


def message(tp, **kwargs):
    jsonified = json.dumps({'type': tp, **kwargs})
    return f'data: {jsonified}\n\n'.encode()
    

server_id = uuid.uuid4().hex

def update_serverid():
    global server_id
    server_id = uuid.uuid4().hex

def serverid_hotreload(request):
    return HttpResponse(f'{{"serverId": "{server_id}"}}')

def eventsource_hotreload(request):
    if not settings.DEBUG:
        raise Http404()

    from .signals import browser_reload_event

    if not request.accepts('text/event-stream'):
        return HttpResponse(status=HTTPStatus.NOT_ACCEPTABLE)

    def event_stream():
        # 立刻发送一个ping，触发浏览器EventSource的open事件。
        yield message('ping')
        while True:
            should_reload = browser_reload_event.wait(timeout=3.0)
            if should_reload:
                browser_reload_event.clear()
                logger.info("trigger browser to reload")
                yield message('reload')
            else:
                # 发送ping，用于检测浏览器页面是否已关闭，关闭则结束这个链接
                yield message('ping')

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream',
    )
    response['content-encoding'] = ''
    return response

hotreload = serverid_hotreload

def components(request):
    pass
