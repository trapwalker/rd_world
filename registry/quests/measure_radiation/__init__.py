# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.classes.quests import Quest, MarkerMapObject, QuestRange, Cancel, QuestState_
from sublayers_server.model.registry_me.tree import IntField, FloatField, ListField, EmbeddedDocumentField, UUIDField

import random


class MeasureRadiation(Quest):
    measuring_price = IntField(caption=u'Стоимость одного замера радиации', tags={'client'})
    measuring_radius = FloatField(caption=u'Максимальный радиус измерения', tags={'client'})
    measure_points_generator = ListField(
        default=[],
        caption=u"Список областей генерации пунктов замеров",
        field=EmbeddedDocumentField(document_type=MarkerMapObject, reinst=True),
        reinst=True
    )
    measure_points = ListField(
        tags={'client'},
        default=[],
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
        default=[],
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
        self.log(text=u'Начат квест по замеру уровня радиации.', event=event, position=self.hirer.hometown.position)


    ## Перечень состояний ##############################################################################################
    #class (QuestState_):
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
        self.text_short = u"Обследуйте {:.0f} точек.".format(self.measure_count)
        self.text = u"Замерьте уровень радиации в {:.0f} точек{}. Награда: {:.0f}nc и {:.0f} кармы.".format(
            self.measure_count,
            u"" if not self.deadline else u" за {}".format(self.deadline_to_str()),
            self.reward_money,
            self.reward_karma,
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
                    self.log(text=u'Произведено измерение.', event=event, position=position)
                    self.measure_notes.remove(note_uid)
                    self.agent.profile.del_note(uid=note_uid, time=event.time)

    def delete_notes(self, event):
        for note_uid in self.measure_notes:
            self.agent.profile.del_note(uid=note_uid, time=event.time)
        self.measure_notes = []
