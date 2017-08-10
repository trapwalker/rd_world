# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.quest_events import OnCancel, OnTimer, OnNote, OnKill
from sublayers_server.model.registry_me.classes.quests import (
    Cancel, QuestState_, FailByCancelState, FailState, WinState,
)
from sublayers_server.model.registry_me.tree import (IntField, FloatField, ListField, EmbeddedDocumentField,
                                                     BooleanField, Subdoc, StringField, UUIDField)
from sublayers_server.model.registry_me.classes.quests import Quest, QuestRange
from sublayers_server.model.utils import getKarmaName

from functools import partial
import random


class EscortCaravan(Quest):
    caravan_quest_uid = StringField(caption=u'UID квеста-события из диспетчера задач. Как только по этому UID не будет найден квест - переход в состояние победы')

    def as_client_dict(self):
        d = super(EscortCaravan, self).as_client_dict()
        # d.update()
        return d

    def as_unstarted_quest_dict(self):
        d = super(EscortCaravan, self).as_unstarted_quest_dict()
        # d.update(count_to_kill=self.count_to_kill,)
        return d

    def get_caravan_quest(self, event):
        if self.caravan_quest_uid:
            # Поискать из списка. Если не найден, то квест считается выполненым
            return event.server.ai_dispatcher.get_quest_by_uid(uid=self.caravan_quest_uid)
        # Попробовать найти караван, отправляющийся из города А в город Б

    def can_generate(self, event):
        caravan_quest = self.get_caravan_quest(event=event)

    ####################################################################################################################
    def on_generate_(self, event, **kw):
        if not self.can_generate(event):
            raise Cancel("QUEST CANCEL: reason: Active caravan not found")

    ####################################################################################################################
    def on_start_(self, event, **kw):
        pass
    
    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.set_timer(event=event, name='caravan_end_test', delay=5)
    
        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            if isinstance(event, OnTimer) and event.name == 'caravan_end_test':
                caravan_quest = quest.get_caravan_quest(event=event)
                # todo: как-то проверить: сбросили квест после рестарта или караван реально доехал
                if caravan_quest is None:
                    go("win")

    ####################################################################################################################
    class cancel_fail(FailByCancelState):
        def on_enter_(self, quest, event):
            quest.log(text=u'Квест провален: отказ от выполнения.', event=event)

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
           quest.log(text=u'Квест выполнен.', event=event)

    ####################################################################################################################