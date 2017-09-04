# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.quest_events import OnCancel, OnTimer, OnNote, OnActivateItem
from sublayers_server.model.registry_me.classes.quests import (
    Cancel, QuestState_, FailByCancelState, FailState, WinState,
)
from sublayers_server.model.registry_me.tree import (IntField, FloatField, ListField, EmbeddedDocumentField, UUIDField,
                                                     EmbeddedNodeField, LocalizedString)
from sublayers_server.model.registry_me.classes.quests import Quest, MarkerMapObject

from functools import partial
import random


class MapActivateItemQuest(Quest):
    activate_price = IntField(caption=u'Стоимость одной активации итема', tags={'client'})
    activate_radius = FloatField(caption=u'Максимальный радиус активации', tags={'client'})

    activate_points_generator = ListField(
        root_default=list,
        caption=u"Список областей генерации пунктов замеров",
        field=EmbeddedDocumentField(document_type=MarkerMapObject),
        reinst=True,
    )
    activate_points = ListField(
        root_default=list,
        caption=u"Список областей генерации пунктов замеров",
        field=EmbeddedDocumentField(document_type=MarkerMapObject),
        reinst=True,
    )

    activate_items_generator = ListField(
        caption=u"Список возможных итемов для активации",
        field=EmbeddedNodeField(
            document_type='sublayers_server.model.registry_me.classes.item.Item',
            caption=u"Необходимый итем",
            reinst=True,
            tags={'client'},
        )
    )
    activate_items = ListField(
        caption=u"Список итемов для доставки",
        field=EmbeddedNodeField(
            document_type='sublayers_server.model.registry_me.classes.item.Item',
            caption=u"Необходимый итем",
            reinst=True,
            tags={'client'},
        ),
    )

    activate_notes = ListField(
        root_default=list,
        caption=u"Список активных нотов маркеров на карте",
        field=UUIDField(),
        reinst=True,
    )

    def init_activate_points(self):
        self.activate_points = []
        for i in range(0, random.randint(3, 6)):
            base_point = random.choice(self.activate_points_generator)
            self.activate_points.append(MarkerMapObject(position=base_point.generate_random_point(),
                                                    radius=self.activate_radius))

    def init_activate_items(self):
        self.activate_items = []
        choice = random.choice(self.activate_items_generator)
        need_count = len(self.activate_points)
        count = 0
        while count < need_count:
            amount = min(choice.stack_size, need_count - count)
            count += amount
            if amount:
                item = choice.instantiate(amount=amount)
                self.activate_items.append(item)

    def init_distance(self):
        p1 = self.hirer.hometown.position.as_point()
        p2 = self.activate_points[0].position.as_point()
        return p1.distance(p2) * 2  #  дистация двойная, так как нужно съездить туда и обратно

    def init_deadline(self, distance=0):
        # Время выделенное на квест в секундах
        if self.design_speed:
            all_time = int(distance / self.design_speed)
            # Время выделенное на квест кратно 5 минутам
            self.deadline = (all_time / 300) * 300 + (300 if (all_time % 300) > 0 else 0)
        else:
            self.deadline = 0

    def init_text(self):
        self.text_short = LocalizedString(
            en=u"Активируйте предметы в заданных точках.",  # TODO: ##LOCALIZATION
            ru=u"Активируйте предметы в заданных точках.",
        )
        self.text = LocalizedString(
            en=u"Активируйте предметы: {} - в заданных точках. Награда: {:.0f}nc.".format(  # TODO: ##LOCALIZATION
                ', '.join([unicode(item.title) for item in self.activate_items]),
                self.reward_money,
            ),
            ru=u"Активируйте предметы: {} - в заданных точках. Награда: {:.0f}nc.".format(
                ', '.join([unicode(item.title) for item in self.activate_items]),
                self.reward_money,
            ),
        )

    def init_notes(self, event):
        for point in self.activate_points:
            note_uid = self.agent.profile.add_note(
                quest_uid=self.uid,
                note_class=notes.MapMarkerNote,
                time=event.time,
                position=point.position,
                radius=point.radius,
            )
            self.activate_notes.append(note_uid)

    def check_notes(self, event):
        if not self.agent.profile._agent_model or not self.agent.profile._agent_model.car:
            return

        temp_notes = self.activate_notes[:]
        for note_uid in temp_notes:
            note = self.agent.profile.get_note(note_uid)
            if note:
                position = self.agent.profile._agent_model.car.position(time=event.time)
                if note.is_near(position=position):
                    self.log(text=self.locale("q_ai_do_activate"), event=event, position=position)  # ##LOCALIZATION
                    self.agent.profile.set_exp(time=event.time, dvalue=self.reward_exp)
                    self.activate_notes.remove(note_uid)
                    self.agent.profile.del_note(uid=note_uid, time=event.time)
                    return # Если вдруг позиции рядом, чтобы не засчиталась одна активация нескольким нотам

    def check_item(self, item):
        return self.activate_items[0].node_hash() == item.node_hash()

    def delete_notes(self, event):
        for note_uid in self.activate_notes:
            self.agent.profile.del_note(uid=note_uid, time=event.time)
        self.activate_notes = []

    ####################################################################################################################
    def on_generate_(self, event, **kw):
        if not self.can_generate(event):
            raise Cancel("QUEST CANCEL: reason: generate rules")

        if not self.activate_points_generator:
            raise Cancel("QUEST ActivateItems CANCEL: Empty generator list.")
        if not self.activate_items_generator:
            raise Cancel("QUEST ActivateItems CANCEL: Empty empty delivery_set_list.")
        if self.hirer.hometown is None:
            raise Cancel("QUEST ActivateItems CANCEL: {} hometown is None.".format(self.hirer.hometown))

        self.init_level()
        self.init_activate_points()
        self.init_activate_items()
        distance = self.init_distance()
        self.init_deadline(distance)

        cost_delivery_items = 0
        for item in self.activate_items:
            cost_delivery_items += item.base_price * item.amount / item.stack_size
        distance_cost = self.get_distance_cost(distance=distance)

        if distance_cost == 0:
            log.warning('MapActivateItemQuest Quest: Warning!!! ')

        self.total_reward_money = cost_delivery_items + distance_cost
        self.generate_reward()  # Устанавливаем награду за квест (карму, деньги и итемы)
        self.init_text()  # Инициализируем строку описания квеста
    
    ####################################################################################################################
    def on_start_(self, event, **kw):
        if not self.give_items(items=self.activate_items, event=event):
            self.npc_replica(npc=self.hirer, replica=self.locale("q_share_no_inv_slot"), event=event)  # ##LOCALIZATION
            raise Cancel("QUEST CANCEL: User have not enough empty slot")
        self.log(text=self.locale("q_ai_start_text"), event=event, position=self.hirer.hometown.position)  # ##LOCALIZATION
    
    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            # Создание таймера deadline
            if self.deadline:
                self.set_timer(name='deadline_activate_quest', delay=self.deadline, event=event)
            self.init_notes(event=event)
    
        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent
            if isinstance(event, OnCancel):
                penalty_money = quest.reward_money / 2.
                if agent.profile.balance >= penalty_money:
                    agent.profile.set_balance(time=event.time, delta=-penalty_money)
                    quest.log(text=u'{} {}nc.'.format(quest.locale("q_share_cancel_pen_done"), penalty_money), event=event,  # ##LOCALIZATION
                              position=quest.hirer.hometown.position)
                    go("cancel_fail")
                else:
                    quest.npc_replica(npc=quest.hirer,
                                      replica=u"{} {}nc.".format(quest.locale("q_share_cancel_pen_try"), penalty_money),  # ##LOCALIZATION
                                      event=event)
            if isinstance(event, OnTimer):
                if event.name == 'deadline_activate_quest':
                    go("fail")
            if isinstance(event, OnActivateItem) and quest.check_item(item=event.item_example):
                quest.check_notes(event=event)
                if len(quest.activate_notes) == 0:
                    go("reward")

    ####################################################################################################################
    class reward(QuestState_):
        def on_enter_(self, quest, event):
            agent = quest.agent
            agent.profile.set_relationship(time=event.time, npc=quest.hirer, dvalue=quest.reward_relation_hirer)
            quest.dc.reward_note_uid = agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.MapActivationNoteFinish,
                time=event.time,
                npc=quest.hirer,
                page_caption=quest.locale("q_ai_note_caption"),  # ##LOCALIZATION
                btn1_caption=quest.locale("q_ai_note_btn1"),  # ##LOCALIZATION
            )
    
        def on_event_(self, quest, event):
            agent = quest.agent
            go = partial(quest.go, event=event)
            if isinstance(event, OnNote):
                if (event.note_uid == quest.dc.reward_note_uid) and (event.result == True):
                    agent.profile.set_balance(time=event.time, delta=quest.reward_money)
                    agent.profile.del_note(uid=quest.reward_note_uid, time=event.time)
                    go('win')

    ####################################################################################################################
    class cancel_fail(FailByCancelState):
        def on_enter_(self, quest, event):
            quest.delete_notes(event=event)
            quest.log(text=quest.locale("q_share_q_fail"), event=event)  # ##LOCALIZATION

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.delete_notes(event=event)
            quest.log(text=quest.locale("q_share_q_win"), event=event)  # ##LOCALIZATION

    ####################################################################################################################
    class fail(FailState):
        def on_enter_(self, quest, event):
            quest.delete_notes(event=event)
            quest.agent.profile.set_relationship(time=event.time, npc=quest.hirer,
                                           dvalue=-quest.level * 2)  # изменение отношения c нпц
            quest.agent.profile.set_karma(time=event.time, dvalue=-quest.reward_karma)  # изменение кармы
            quest.log(text=quest.locale("q_share_q_fail"), event=event)  # ##LOCALIZATION
    ####################################################################################################################