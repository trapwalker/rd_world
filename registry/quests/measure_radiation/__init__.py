# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import IntField, FloatField, ListField, EmbeddedDocumentField, UUIDField, LocalizedString
from sublayers_server.model.quest_events import OnCancel, OnTimer, OnNote
from sublayers_server.model.registry_me.classes.quests import (
    Quest, MarkerMapObject, QuestRange, Cancel,
    QuestState_, FailByCancelState, FailState, WinState,
)

import random
from functools import partial


class MeasureRadiation(Quest):
    measuring_price = IntField(caption=u'Стоимость одного замера радиации', tags={'client'})
    measuring_radius = FloatField(caption=u'Максимальный радиус измерения', tags={'client'})
    measure_points_generator = ListField(
        root_default=list,
        caption=u"Список областей генерации пунктов замеров",
        field=EmbeddedDocumentField(document_type=MarkerMapObject, reinst=True),
        reinst=True
    )
    measure_points = ListField(
        tags={'client'},
        root_default=list,
        caption=u"Список выбранных пунктов для замеров",
        field=EmbeddedDocumentField(
            document_type='sublayers_server.model.registry_me.classes.quests2.MarkerMapObject'
        ),
        reinst=True,
    )
    measure_count_range = EmbeddedDocumentField(
        document_type=QuestRange,
        caption=u"Диапазон количетсва измерений",
        reinst=True,
    )
    measure_count = IntField(caption=u'Количество замеров', tags={'client'})
    measure_notes = ListField(
        root_default=list,
        caption=u"Список активных нотов маркеров на карте",
        field=UUIDField(),
        reinst=True,
    )
    ####################################################################################################################
    def on_generate_(self, event, **kw):
        # TODO: Clean deprecated root handler and add super call then
        if not self.can_generate(event):
            raise Cancel("QUEST CANCEL: reason: generate rules")

        if self.hirer.hometown is None:
            raise Cancel("QUEST MeasureRadiation CANCEL: {} hometown is None.".format(self.hirer.hometown))

        if not self.measure_points_generator:
            raise Cancel("QUEST MeasureRadiation CANCEL: Empty generator list.")
        self.init_measure_points()

        self.init_level()
        self.init_deadline()

        self.total_reward_money = self.measuring_price * self.measure_count
        self.generate_reward()  # Устанавливаем награду за квест (карму, деньги и итемы)
        self.init_text() # Инициализируем строку описания квеста

    ####################################################################################################################
    def on_start_(self, event, **kw):
        self.log(text=self.locale("q_mr_start_text"), event=event, position=self.hirer.hometown.position)  ##LOCALIZATION


    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            # Создание таймера deadline
            if quest.deadline:
                quest.set_timer(event=event, name='deadline_measuring_quest', delay=quest.deadline)

            quest.set_timer(event=event, name='test_measuring_quest', delay=5)
            quest.init_notes(event=event)
            q_item = event.server.reg.get('/registry/items/quest_item/quest_item_1').instantiate()
            quest.agent.profile.quest_inventory.add_item(agent=quest.agent, item=q_item, event=event)
            # todo: Разобраться почему quest_inventory.add_item требует в аргументах агента

        def on_event_(self, quest, event):
            agent = quest.agent
            go = partial(quest.go, event=event)
            set_timer = partial(quest.set_timer, event=event)

            if isinstance(event, OnCancel):
                penalty_money = quest.reward_money / 2.
                if agent.profile.balance >= penalty_money:
                    agent.profile.set_balance(time=event.time, delta=-penalty_money)
                    quest.log(text=u'{} {}nc.'.format(quest.locale("q_mr_cancel_pen_done"), penalty_money), event=event, position=quest.hirer.hometown.position)  ##LOCALIZATION
                    go("cancel_fail")
                else:
                   quest.npc_replica(npc=quest.hirer, replica=u"{} {}nc.".format(quest.locale("q_mr_cancel_pen_try"), penalty_money), event=event)  ##LOCALIZATION

            if isinstance(event, OnTimer):
                if event.name == 'deadline_measuring_quest':
                    go("fail")
                if event.name == 'test_measuring_quest':
                    quest.check_notes(event=event)
                    if len(quest.measure_notes) == 0:
                        go("reward")
                    else:
                        set_timer(name='test_measuring_quest', delay=5)
    ####################################################################################################################
    class reward(QuestState_):
        def on_enter_(self, quest, event):
            agent = quest.agent

            quest.log(text=quest.locale("q_mr_do_measure_done"), event=event, position=quest.hirer.hometown.position)  ##LOCALIZATION
            agent.profile.set_relationship(time=event.time, npc=quest.hirer, dvalue=quest.reward_relation_hirer)
            quest.dc.reward_note_uid = agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.QuestRadiationNPCFinish,
                time=event.time,
                npc=quest.hirer,
                page_caption=quest.locale("q_mr_note_caption"),  ##LOCALIZATION
                btn1_caption=quest.locale("q_mr_note_btn1"),  ##LOCALIZATION
            )

        def on_event_(self, quest, event):
            agent = quest.agent
            go = partial(quest.go, event=event)

            if isinstance(event, OnNote):
                # review: event.result == True
                if (event.note_uid == quest.dc.reward_note_uid) and (event.result == True):
                    agent.profile.set_balance(time=event.time, delta=quest.reward_money)
                    agent.profile.del_note(uid=quest.dc.reward_note_uid, time=event.time)
                    go('win')
    ####################################################################################################################
    class cancel_fail(FailByCancelState):
        def on_enter_(self, quest, event):
            quest.delete_notes(event=event)
            quest.log(text=quest.locale("q_share_q_fail"), event=event)  ##LOCALIZATION
    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.delete_notes(event=event)
            quest.log(text=quest.locale("q_share_q_win"), event=event)  ##LOCALIZATION
    ####################################################################################################################
    class fail(FailState):
        def on_enter_(self, quest, event):
            quest.delete_notes(event=event)
            quest.agent.profile.set_relationship(time=event.time, npc=quest.hirer, dvalue=-quest.level * 2)  # изменение отношения c нпц
            quest.agent.profile.set_karma(time=event.time, dvalue=-quest.reward_karma)  # изменение кармы
            quest.log(text=quest.locale("q_share_q_fail"), event=event)  ##LOCALIZATION
    ####################################################################################################################
    ####################################################################################################################
    def init_measure_points(self):
        self.measure_count = self.measure_count_range.get_random_int()
        for i in range(self.measure_count):
            base_point = random.choice(self.measure_points_generator)
            self.measure_points.append(MarkerMapObject(position=base_point.generate_random_point(),
                                                       radius=self.measuring_radius))
    def init_deadline(self):
        if self.deadline:
            all_time = self.measure_count * self.deadline
            # Время выделенное на квест кратно 5 минутам
            self.deadline = (all_time / 300) * 300 + (300 if (all_time % 300) > 0 else 0)

    def init_text(self):
        self.text_short = LocalizedString(
            en=u"Inspect {:.0f} points.".format(self.measure_count),   ##LOCALIZATION
            ru=u"Обследуйте {:.0f} точек.".format(self.measure_count),
        )
        self.text = LocalizedString(
            en=u"Measure radiation level in {:.0f} points{}. Reward: {:.0f}nc, {:.0f} karma and {:.0f} exp. points".format(   ##LOCALIZATION
                self.measure_count,
                u"" if not self.deadline else u" for {}".format(self.deadline_to_str()),   ##LOCALIZATION
                self.reward_money,
                self.reward_karma,
                self.reward_exp * self.measure_count,
            ),
            ru=u"Замерьте уровень радиации в {:.0f} точек{}. Награда: {:.0f}nc, {:.0f} кармы и {:.0f} ед. опыта".format(
                self.measure_count,
                u"" if not self.deadline else u" за {}".format(self.deadline_to_str()),   ##LOCALIZATION
                self.reward_money,
                self.reward_karma,
                self.reward_exp * self.measure_count,
            ),
        )

    def init_notes(self, event):
        for marker in self.measure_points:
            note_uid = self.agent.profile.add_note(
                quest_uid=self.uid,
                note_class=notes.MapMarkerNote,
                time=event.time,
                position=marker.position,
                radius=marker.radius,
            )
            self.measure_notes.append(note_uid)

    def check_notes(self, event):
        if not self.agent.profile._agent_model or not self.agent.profile._agent_model.car:
            return

        temp_notes = self.measure_notes[:]
        for note_uid in temp_notes:
            note = self.agent.profile.get_note(note_uid)
            if note:
                position = self.agent.profile._agent_model.car.position(time=event.time)
                if note.is_near(position=position):
                    self.log(text=self.locale("q_mr_do_measure"), event=event, position=position)  ##LOCALIZATION
                    self.agent.profile.set_exp(time=event.time, dvalue=self.reward_exp)
                    self.measure_notes.remove(note_uid)
                    self.agent.profile.del_note(uid=note_uid, time=event.time)

    def delete_notes(self, event):
        for note_uid in self.measure_notes:
            self.agent.profile.del_note(uid=note_uid, time=event.time)
        self.measure_notes = []
