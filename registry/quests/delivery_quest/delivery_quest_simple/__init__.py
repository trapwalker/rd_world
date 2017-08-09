# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import IntField, RegistryLinkField, ListField
from sublayers_server.model.quest_events import OnCancel, OnTimer, OnNote, OnEnterToLocation
from sublayers_server.model.registry_me.classes.quests import (
    Cancel, QuestState_, FailByCancelState, FailState, WinState,
)

from functools import partial
import random


from sublayers_world.registry.quests.delivery_quest import DeliveryQuest

from ctx_timer import T


class DeliveryQuestSimple(DeliveryQuest):
    def get_available_lvl(self):
        relation = self.agent.profile.get_relationship(npc=self.hirer)
        lvl_table = [-0.8, -0.6, 0.4, -0.2, 0, 0.2, 0.4, 0.6, 0.8, 1]
        for item in lvl_table:
            if relation < item:
                return lvl_table.index(item)
        return len(lvl_table)

    def init_level(self):
        self.level = self.get_available_lvl()

        # Этот код нужен чтобы всегда генерить хотябы самый слабый квест
        if self.level == 0:
            self.level = 1

        self.level = random.randint(1, self.level)

    def init_delivery_set(self):
        self.delivery_set = []
        for i in range(self.level + 3):
            # Выбор только по первому элементу списка (т.к. в простой реализации квеста естьтолько список итемов а не пресеты)
            choice = random.choice(self.delivery_set_list[0])
            item = choice.instantiate(amount=choice.amount)
            self.delivery_set.append(item)

    def init_distance(self):
        town1 = self.hirer.hometown
        town2 = self.recipient.hometown
        return self.distance_table.get_distance(town1=town1, town2=town2)

    def init_deadline(self, distance):
        # Время выделенное на квест в секундах
        all_time = distance / 14

        # Время выделенное на квест кратно 5 минутам
        self.deadline = (all_time / 300) * 300 + (300 if (all_time % 300) > 0 else 0)

    ####################################################################################################################
    def on_generate_(self, event, **kw):
        if not self.can_generate(event):
            raise Cancel("QUEST CANCEL: reason: generate rules")
        self.init_level()
        # todo: Здесь строки! нужно иметь это ввиду
        uri = random.choice(self.recipient_list)
        try:
            r = event.server.reg.get(uri)
        except:
            raise Cancel("QUEST CANCEL: uri<{}>  not resolve.".format(uri))
        self.recipient = r

        self.init_delivery_set()

        cost_delivery_items = 0
        for item in self.delivery_set:
            cost_delivery_items += item.base_price * item.amount / item.stack_size

        if self.recipient.hometown is None:
            raise Cancel("QUEST CANCEL: {} hometown is None.".format(self.recipient.hometown))
        if self.hirer.hometown is None:
            raise Cancel("QUEST CANCEL: {} hometown is None.".format(self.hirer.hometown))

        distance = self.init_distance()
        self.init_deadline(distance)

        distance_cost = round(distance / 1000)  # todo: уточнить стоимость 1px пути

        if distance_cost == 0:
            log.warning('DeliverySimple Quest: Warning!!! Distance from hirer<{!r}> to recipient<{!r}> = {}. Change recipient'.format(
                self.hirer, self.recipient, distance))

        self.total_reward_money = self.total_delivery_money_coef * cost_delivery_items + distance_cost
        self.generate_reward()  # Устанавливаем награду за квест (карму, деньги и итемы)
        self.init_text(distance)  # Инициализируем строку описания квеста

    ####################################################################################################################
    def on_start_(self, event, **kw):
        if self.get_available_lvl() < self.level:
            raise Cancel("QUEST CANCEL: User have not enough relation")
        if not self.give_items(items=self.delivery_set, event=event):
            self.npc_replica(npc=self.hirer, replica=u"Не хватает места в инвентаре.", event=event)
            raise Cancel("QUEST CANCEL: User have not enough empty slot")

        self.log(text=u'Начат квест по доставке.', event=event, position=self.hirer.hometown.position)
        temp_log_str = u'От {} получены следующие предметы: {}.'.format(
            self.hirer.title,
            ', '.join([item.title for item in self.delivery_set])
        )
        self.log(text=temp_log_str, event=event, position=self.hirer.hometown.position)

    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            go = partial(quest.go, event=event)
            quest.dc.delivery_note_uid = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.NPCDeliveryNote,
                time=event.time,
                npc=quest.recipient,
                page_caption="Доставка<br>груза",
            )
            go('delivery')

    class delivery(QuestState_):
        def on_enter_(self, quest, event):
            quest.set_timer(event=event, name='deadline', delay=quest.deadline)

        def on_event_(self, quest, event):
            agent = quest.agent
            go = partial(quest.go, event=event)

            if isinstance(event, OnNote):
                if (event.note_uid == quest.dc.delivery_note_uid) and (event.result == True) and quest.take_items(
                        items=quest.delivery_set, event=event):
                    temp_log_str = u'{} забрал следующие предметы: {}.'.format(
                        quest.recipient.title,
                        ', '.join([item.title for item in quest.delivery_set])
                    )
                    quest.log(text=temp_log_str, event=event, position=quest.recipient.hometown.position)
                    agent.profile.del_note(uid=quest.dc.delivery_note_uid, time=event.time)
                    go('reward')
            if isinstance(event, OnTimer) and (event.name == 'deadline'):
                agent.profile.del_note(uid=quest.dc.delivery_note_uid, time=event.time)
                go("fail")
            if isinstance(event, OnCancel):
                if quest.can_take_items(items=quest.delivery_set, event=event) and (
                    agent.profile.balance >= (quest.reward_money / 2)):
                    agent.profile.del_note(uid=quest.dc.delivery_note_uid, time=event.time)
                    quest.take_items(items=quest.delivery_set, event=event)
                    agent.profile.set_balance(time=event.time, delta=-(quest.reward_money / 2))

                    temp_log_str = u'{} забрал следующие предметы: {}.'.format(
                        quest.hirer.title,
                        ', '.join([item.title for item in quest.delivery_set])
                    )
                    quest.log(text=temp_log_str, event=event, position=quest.hirer.hometown.position)
                    quest.log(text=u'Уплачен штраф в размере {}nc.'.format(quest.reward_money / 2), event=event,
                              position=quest.hirer.hometown.position)

                    go("cancel_fail")
                else:
                    quest.npc_replica(npc=quest.hirer,
                                      replica=u"Для отказа от квеста верните итемы и заплатите штраф {}nc.".format(
                                          quest.reward_money / 2), event=event)

    ####################################################################################################################
    class reward(QuestState_):
        def on_enter_(self, quest, event):
            go = partial(quest.go, event=event)
            agent_profile = quest.agent.profile
            quest.agent.profile.set_balance(time=event.time, delta=quest.reward_money)
            quest.log(text=u'Получено вознаграждение в размере {}nc.'.format(quest.reward_money), event=event,
                      position=quest.recipient.hometown.position)
            quest.agent.profile.set_exp(time=event.time, dvalue=quest.reward_exp)
            quest.agent.profile.set_karma(time=event.time, dvalue=quest.reward_karma)
            agent_profile.set_relationship(time=event.time, npc=quest.hirer,
                                           dvalue=quest.reward_relation_hirer)  # изменение отношения к нпц
            if len(quest.reward_items) > 0:
                quest.dc.reward_note_uid = agent_profile.add_note(
                    quest_uid=quest.uid,
                    note_class=notes.NPCRewardItemsNote,
                    time=event.time,
                    npc=quest.recipient,
                    page_caption=u'Награда',
                    btn1_caption=u'<br>Забрать',
                )
            else:
                go('win')

        def on_event_(self, quest, event):
            agent = quest.agent
            go = partial(quest.go, event=event)
            if isinstance(event, OnNote):
                if (event.note_uid == quest.dc.reward_note_uid) and (event.result == True):
                    if quest.give_items(items=quest.reward_items, event=event):
                        agent.profile.del_note(uid=quest.dc.reward_note_uid, time=event.time)
                        go('win')
                    else:
                        quest.npc_replica(npc=quest.hirer, replica=u"Не хватает места в инвентаре.", event=event)

    ####################################################################################################################
    class cancel_fail(FailByCancelState):
        def on_enter_(self, quest, event):
            quest.log(text=u'Квест провален.', event=event)

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=u'Квест выполнен.', event=event)

    ####################################################################################################################
    class fail(FailState):
        def on_enter_(self, quest, event):
            agent_profile = quest.agent.profile
            agent_profile.set_relationship(time=event.time, npc=quest.recipient,
                                           dvalue=-quest.level * 2)  # изменение отношения c нпц
            agent_profile.set_relationship(time=event.time, npc=quest.hirer,
                                           dvalue=-quest.level * 2)  # изменение отношения c нпц
            agent_profile.set_karma(time=event.time, dvalue=-quest.reward_karma)  # todo: изменение кармы
            quest.log(text=u'Квест провален.', event=event)


