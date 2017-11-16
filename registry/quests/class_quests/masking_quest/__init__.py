# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import QuestState_, WinState, QuestRange, MarkerMapObject
from sublayers_server.model.quest_events import OnNote, OnTimer, OnDie
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.slave_objects.turret import MaskingQuestTurret
from functools import partial
from sublayers_server.model.registry_me.tree import (
    Subdoc, LocalizedString,
    MapField, ListField,
    LocalizedStringField,
    EmbeddedDocumentField,
    RegistryLinkField,
)
from sublayers_world.registry.quests.class_quests import ClassTypeQuest
from sublayers_server.model.vectors import Point
from math import pi
import random


class MaskingQuest(ClassTypeQuest):
    radius_range = EmbeddedDocumentField(document_type=QuestRange, reinst=True)
    container_position = EmbeddedDocumentField(document_type=MarkerMapObject, reinst=False)

    class RoleClassQuestAttributes(Subdoc):
        next_quest = RegistryLinkField(
            caption=u"Прототип классового квеста",
            document_type='sublayers_server.model.registry_me.classes.quests.Quest',
            root_default='reg:///registry/quests/class_quests/start_quest'
        )
        class_item = RegistryLinkField(
            document_type='sublayers_server.model.registry_me.classes.quest_item.QuestItem',
        )

    attributes_by_class = MapField(
        caption=u'Словарь атрибутов',
        field=EmbeddedDocumentField(document_type=RoleClassQuestAttributes),
    )

    def init_text(self):
        self.text = LocalizedString(_id="q_cq_masking_text")  ##LOCALIZATION

    # Тут мы выбираем область в которой будет размещен контейнер с турелью
    def init_container_pos(self):
        position = Point.polar(r=self.radius_range.min + self.radius_range.max * random.random(),
                               fi=2 * pi * random.random()) +\
                   Point(self.hirer.hometown.position.x, self.hirer.hometown.position.y)
        self.container_position = MarkerMapObject(position=position, radius=30)

    # Тут мы размещаем контейнер и турель
    def init_container(self):
        pass

    def on_start_(self, event, **kw):
        # Определяем следующий квест
        role_class = self.agent.profile.role_class
        class_attrs = self.attributes_by_class.get(role_class.name, None)
        self.next_quest = class_attrs.next_quest

        self.dc.masking_npc_note = None

        self.init_text()
        self.log(text=self.locale("q_cq_masking_started"), event=event)  ##LOCALIZATION


    ####################################################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.init_container_pos()
            if not quest.dc.masking_npc_note:
                quest.dc.masking_npc_note = quest.agent.profile.add_note(
                    quest_uid=quest.uid,
                    note_class=notes.MaskingNPCQuestNote,
                    time=event.time,
                    page_caption=quest.locale("q_cq_masking_npc_note_caption"),
                    btn1_caption=quest.locale("q_cq_masking_npc_note_btn"),
                    npc=quest.hirer,
                )
            quest.dc.container_map_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.MaskingMapMarkerNote,
                time=event.time,
                position=quest.container_position.position,
                radius=quest.container_position.radius
            )

            # Таймер проверки достигли ли мы зоны тайника
            quest.set_timer(event=event, name='test_masking_point_begin', delay=10)

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent_profile = quest.agent.profile

            if isinstance(event, OnTimer) and (event.name == 'test_masking_point_begin'):
                if agent_profile._agent_model and agent_profile._agent_model.car and \
                        quest.container_position.is_near(
                            position=agent_profile._agent_model.car.position(time=event.time),
                            radius=2000,  # турель поместится на карту когда мы подъедим на расстояние 2км
                        ):
                    go("masking")
                else:
                    quest.set_timer(event=event, name='test_masking_point_begin', delay=10)

    ####################################################################################################################
    class masking(QuestState_):
        def on_enter_(self, quest, event):
            quest.init_container()

            # Создаем турель
            turret_position = Point.random_point(radius=200, center=quest.container_position.position.as_point())
            turret_example = event.server.reg.get('reg:///registry/mobiles/map_weapon/stationary/turret/masking_quest_turret')
            turret = MaskingQuestTurret(
                time=event.time,
                position=turret_position,
                starter=quest.agent.profile._agent_model.car,
                example=turret_example
            )
            quest.dc.turret_uid = turret.uid

            # Нота турели
            quest.dc.turret_map_note = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.MaskingTurretMapMarkerNote,
                time=event.time,
                position=turret_position,
                radius=turret_example.p_observing_range,
            )
            # Время жизни тайника 8 часов
            quest.set_timer(event=event, name='deadline_masking_point', delay=28800)
            # Таймер проверки достигли ли мы тайника
            quest.set_timer(event=event, name='test_masking_point', delay=5)

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent_profile = quest.agent.profile

            # Если вышло 8 часов или нас убили, то начать с начала
            if isinstance(event, OnTimer) and (event.name == 'deadline_masking_point'):
                turret = event.server.objects.get(quest.dc.turret_uid, None)
                if turret and turret.is_alive:
                    turret.delete(time=event.time)
                agent_profile.del_note(uid=quest.dc.turret_map_note, time=event.time)
                agent_profile.del_note(uid=quest.dc.container_map_note, time=event.time)
                go("begin")

            # Проверить не находимся ли мы уже рядом с тайником
            if isinstance(event, OnTimer) and (event.name == 'test_masking_point'):
                if agent_profile._agent_model and agent_profile._agent_model.car and \
                        quest.container_position.is_near(position=agent_profile._agent_model.car.position(time=event.time)):
                    turret = event.server.objects.get(quest.dc.turret_uid, None)
                    if turret and turret.is_alive:
                        turret.delete(time=event.time)
                    agent_profile.del_note(uid=quest.dc.turret_map_note, time=event.time)
                    agent_profile.del_note(uid=quest.dc.container_map_note, time=event.time)

                    # Выдаем классовый предмет
                    class_attrs = quest.attributes_by_class.get(agent_profile.role_class.name, None)
                    if class_attrs:
                        class_item = class_attrs.class_item.instantiate()
                        agent_profile.quest_inventory.add_item(agent=quest.agent, item=class_item, event=event)
                    else:
                        log.warninig('role class %r is not supported in ClassQuest', agent_profile.role_class)
                        return
                    go("to_trainer")
                else:
                    quest.set_timer(event=event, name='test_masking_point', delay=5)

    ####################################################################################################################
    class to_trainer(QuestState_):
        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent_profile = quest.agent.profile

            if isinstance(event, OnNote) and (event.note_uid == quest.dc.masking_npc_note):
                agent_profile.del_note(uid=quest.dc.masking_npc_note, time=event.time)
                go("win")

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_cq_final"), event=event)  ##LOCALIZATION
            agent_example = quest.agent
            new_quest = quest.next_quest.instantiate(abstract=False, hirer=quest.hirer)
            if new_quest.generate(event=event, agent=agent_example):
                agent_example.profile.add_quest(quest=new_quest, time=event.time)
                new_quest.start(server=event.server, time=event.time + 0.1)
            else:
                del new_quest