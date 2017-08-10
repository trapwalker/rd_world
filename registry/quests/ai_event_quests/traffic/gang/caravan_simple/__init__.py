# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_world.registry.quests.ai_event_quests.traffic.gang import AIGangQuest
from sublayers_server.model.registry_me.tree import EmbeddedDocumentField

from sublayers_server.model.registry_me.classes.quests import QuestState_, QuestRange
from sublayers_server.model.quest_events import OnTimer
from functools import partial


class AICaravanQuest(AIGangQuest):
    caravan_wait_time = EmbeddedDocumentField(document_type=QuestRange, caption=u"Границы задержки перед стартом каравана (минуты)")

    def on_see_object(self, event):  # Вызывается когда только для OnAISee
        return

    def set_actions(self, time):  # Настройка поведенческих квестов
        self.set_main_cc()  # Корректируем скорость группы (вдруг самый медленный сдох)


    ####################################################################################################################
    def on_generate_(self, event, **kw):
        super(AICaravanQuest, self).on_generate_(event=event, **kw)

    ####################################################################################################################
    def on_start_(self, event, **kw):
        super(AICaravanQuest, self).on_start_(event=event, **kw)
        self.dc.start_caravan_deadline = self.caravan_wait_time.get_random_int() * 60
        self.dc.start_caravan_time = event.time + self.dc.start_caravan_deadline

    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class pre_begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.agent.profile._agent_model.on_event_quest(time=event.time, quest=quest)
            log.debug('Caravan started in: %ss', quest.dc.start_caravan_deadline)
            quest.set_timer(event=event, name='start_caravan', delay=quest.dc.start_caravan_deadline)

        def on_event_(self, quest, event):
            if isinstance(event, OnTimer) and event.name == 'start_caravan':
                go = partial(quest.go, event=event)
                go('begin')

    class begin(QuestState_):
        def on_enter_(self, quest, event):
            log.debug('AICaravanQuest::begin::on_enter_')
            quest.agent.profile._agent_model.on_event_quest(time=event.time, quest=quest)
            quest.set_timer(event=event, name='test_end', delay=quest.test_end_time)
            quest.deploy_bots(event=event)

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            if isinstance(event, OnTimer) and (event.name == 'test_end'):
                status = quest.get_traffic_status(event)
                if status == 'win':
                    quest.displace_bots(event)
                    go('win')
                elif status == 'fail':
                    quest.displace_bots(event)
                    go('fail')
                else:
                    quest.set_timer(event=event, name='test_end', delay=quest.test_end_time)
                    quest.set_actions(time=event.time)
                    quest.set_target_point(time=event.time)
    ####################################################################################################################


