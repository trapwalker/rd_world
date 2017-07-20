# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.quest_events import OnCancel, OnTimer, OnNote, OnActivateItem
from sublayers_server.model.registry_me.classes.quests import (
    Cancel, QuestState_, FailByCancelState, FailState, WinState,
)
from sublayers_world.registry.quests.map_activate_item import MapActivateItemQuest

from functools import partial


class MapActivateRadarsQuest(MapActivateItemQuest):
    def init_distance(self):
        return 0

    def init_deadline(self):
        self.deadline = len(self.activate_points) * 3600  # По часу на точку

    def init_text(self):
        self.text_short = u"Установить наблюдательные зонды."
        self.text = u"Установите в заданных точках наблюдательные зонды в количестве: {}. Награда: {:.0f}nc и {:.0f} ед. опыта".format(
            len(self.activate_points),
            self.reward_money,
            self.reward_exp * len(self.activate_points),
        )

    def generate_reward(self):
        self.reward_money = self.activate_price * len(self.activate_points)
        self.reward_karma = 1

    ####################################################################################################################
    def on_generate_(self, event, **kw):
        if not self.can_generate(event):
            raise Cancel("QUEST CANCEL: reason: generate rules")

        if not self.activate_points_generator:
            raise Cancel("QUEST ActivateRadiation CANCEL: Empty points generator list.")
        if not self.activate_items_generator:
            raise Cancel("QUEST ActivateRadiation CANCEL: Empty empty Items generator list.")
        if self.hirer.hometown is None:
            raise Cancel("QUEST ActivateRadiation CANCEL: {} hometown is None.".format(self.hirer.hometown))

        self.init_level()
        self.init_activate_points()
        self.init_activate_items()
        self.init_deadline()

        self.generate_reward()  # Устанавливаем награду за квест (карму, деньги и итемы)
        self.init_text()  # Инициализируем строку описания квеста

    ####################################################################################################################
    def on_start_(self, event, **kw):
        if not self.give_items(items=self.activate_items, event=event):
            self.npc_replica(npc=self.hirer, replica=u"Не хватает места в инвентаре.", event=event)
            raise Cancel("MapActivateRadarsQuest CANCEL: User have not enough empty slot")
        self.log(text=u'Начат квест по установке радаров.', event=event, position=self.hirer.hometown.position)

    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            # Создание таймера deadline
            if quest.deadline:
                quest.set_timer(event=event, name='deadline_activate_quest', delay=quest.deadline)
            quest.init_notes(event=event)

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            if isinstance(event, OnCancel):
                if quest.can_take_items(items=quest.activate_items, event=event):
                    quest.take_items(items=quest.activate_items, event=event)
                    quest.log(text=u'Зонды возвращены.', event=event, position=quest.hirer.hometown.position)
                    go("cancel_fail")
                else:
                    quest.npc_replica(npc=quest.hirer,
                                      replica=u"Для отказа от квеста отдайте зонды в количестве: {}шт.".format(
                                          len(quest.activate_items)), event=event)
            if isinstance(event, OnTimer) and event.name == 'deadline_activate_quest':
                go("fail")
            if isinstance(event, OnActivateItem) and quest.check_item(item=event.item_example):
                quest.check_notes(event=event)
                if len(quest.activate_notes) == 0:
                    go("report")

    ####################################################################################################################
    class report(QuestState_):
        def on_enter_(self, quest, event):
            agent = quest.agent
            quest.log(text=u'Все радары установлены. Вернитесь за наградой.', event=event,
                      position=quest.hirer.hometown.position)
            quest.dc.reward_note_uid = agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.MapActivationRadarsNoteFinish,
                time=event.time,
                npc=quest.hirer,
                page_caption=u'Установка<br>радаров',
                btn1_caption=u'<br>Отчитаться',
            )

        def on_event_(self, quest, event):
            agent = quest.agent
            go = partial(quest.go, event=event)
            if isinstance(event, OnNote) and event.note_uid == quest.dc.reward_note_uid and event.result == True:
                agent.profile.set_relationship(time=event.time, npc=quest.hirer, dvalue=quest.reward_relation_hirer)
                agent.profile.set_balance(time=event.time, delta=quest.reward_money)
                agent.profile.set_karma(time=event.time, dvalue=quest.reward_karma)
                agent.profile.del_note(uid=quest.dc.reward_note_uid, time=event.time)
                go("win")
    ####################################################################################################################
    class cancel_fail(FailByCancelState):
        def on_enter_(self, quest, event):
            quest.agent.profile.set_relationship(time=event.time, npc=quest.hirer, dvalue=-5)  # изменение отношения c нпц
            quest.delete_notes(event=event)
            quest.log(text=u'Квест провален.', event=event)
    ####################################################################################################################
    # class win(WinState):
    #     def on_enter_(self, quest, event):   # info берём от родителя
    #         quest.delete_notes(event=event)
    #         quest.log(text=u'Квест выполнен.', event=event)
    ####################################################################################################################
    class fail(FailState):
        def on_enter_(self, quest, event):
            quest.delete_notes(event=event)
            quest.agent.profile.set_relationship(time=event.time, npc=quest.hirer, dvalue=-20)  # изменение отношения c нпц
            quest.log(text=u'Квест провален.', event=event)
    ####################################################################################################################