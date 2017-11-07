# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.quest_events import OnTimer
from sublayers_server.model.registry_me.classes.quests import Cancel, QuestState_, FailByCancelState, WinState
from sublayers_server.model.registry_me.tree import (ListField, StringField)
from sublayers_server.model.registry_me.classes.quests import Quest
from sublayers_server.model.quest_events import OnCancel

from functools import partial


class AgentEventQuest(Quest):
    event_quest_uid = StringField(caption=u'UID квеста-события из диспетчера задач. Как только по этому UID не будет найден квест - переход в состояние победы')
    needed_tags = ListField(field=StringField(), caption=u"Теги для определения квеста-события")

    def as_unstarted_quest_dict(self):
        d = super(AgentEventQuest, self).as_unstarted_quest_dict()
        d.update(shelf_life_time=self.shelf_life_time)
        return d

    def get_event_quest(self, event):
        if self.event_quest_uid:
            # Поискать из списка. Если не найден, то квест считается выполненым
            return event.server.ai_dispatcher.get_quest_by_uid(uid=self.event_quest_uid)

    def get_potential_event_quest(self, event, agent):
        event_quests = event.server.ai_dispatcher.get_quest_by_tags(set(self.needed_tags))
        npc_view_quests = agent.profile.npc_view_quests
        for event_quest in event_quests:
            flag = False
            for agent_quest in npc_view_quests:
                if isinstance(agent_quest, AgentEventQuest) and agent_quest.event_quest_uid == str(event_quest.uid):
                    flag = True
                    break
            if not flag:
                return event_quest
        return None

    def can_instantiate(self, event, agent, hirer):
        result = super(AgentEventQuest, self).can_instantiate(event=event, agent=agent, hirer=hirer)
        if not result:
            return result
        # Попробовать найти караван по needed_tags тегам
        return self.get_potential_event_quest(event=event, agent=agent) is not None

    def can_generate(self, event):
        event_quest = self.get_potential_event_quest(event=event, agent=self.agent)
        if not event_quest:
            return False
        self.event_quest_uid = str(event_quest.uid)
        return True

    def can_cancel(self, event):
        return True

    def check_unstarted(self, event):
        return (super(AgentEventQuest, self).check_unstarted(event=event) or
                (self.get_event_quest(event=event) is None))

    ####################################################################################################################
    def on_generate_(self, event, **kw):
        if not self.can_generate(event):
            raise Cancel("QUEST CANCEL: reason: Active Event Quest not found")

    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.set_timer(event=event, name='event_end_test', delay=5)

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            if isinstance(event, OnTimer) and event.name == 'event_end_test':
                quest.set_timer(event=event, name='event_end_test', delay=5)
                event_quest = quest.get_event_quest(event=event)
                if event_quest is None:
                    go("win")
                elif event_quest.status == 'win':
                    go('reward')
                elif event_quest.status == 'fail':
                    go('fail')
            if isinstance(event, OnCancel) and quest.can_cancel(event):
                go('cancel_fail')

    ####################################################################################################################
    class cancel_fail(FailByCancelState):
        def on_enter_(self, quest, event):
            pass

    ####################################################################################################################
    class fail(FailByCancelState):
        def on_enter_(self, quest, event):
            pass

    ####################################################################################################################
    class reward(WinState):
        def on_enter_(self, quest, event):
            pass

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
           pass
