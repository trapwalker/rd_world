# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.tree import FloatField, EmbeddedDocumentField, ListField, EmbeddedNodeField, LocalizedString
from sublayers_server.model.quest_events import OnCancel, OnTimer, OnNote
from sublayers_server.model.registry_me.classes.quests import (
    MarkerMapObject, Cancel, QuestState_, FailByCancelState, FailState, WinState,
)

import random
from functools import partial
from sublayers_server.model.poi_loot_objects import CreatePOILootEvent, QuestPrivatePOILoot
from sublayers_server.model.inventory import ItemState
from sublayers_server.model.vectors import Point

from sublayers_world.registry.quests.delivery_quest.delivery_quest_simple import DeliveryQuestSimple


class DeliveryFromCache(DeliveryQuestSimple):
    cache_radius = FloatField(caption=u'Радиус, в котором можно обнаружить тайник', root_default=50)

    cache_points_generator = ListField(
        root_default=list,
        caption=u"Список областей генерации мест для тайника",
        field=EmbeddedDocumentField(document_type=MarkerMapObject),
        reinst=False,
    )
    cache_point = EmbeddedDocumentField(document_type=MarkerMapObject, reinst=False)

    loot_set_list = ListField(
        root_default=list,
        caption=u"Список возможных комплектов ненужных вещей",
        field=ListField(
            caption=u"Комплект ненужных вещей",
            field=EmbeddedNodeField(
                document_type='sublayers_server.model.registry_me.classes.item.Item',
                caption=u"Необходимый итем",
            ),
        ),
    )
    loot_set = ListField(
        caption=u"Список ненужных вещей",
        field=EmbeddedNodeField(
            document_type='sublayers_server.model.registry_me.classes.item.Item',
            caption=u"Необходимый итем",
        ),
    )

    def init_level(self):
        self.level = 1

    def generate_reward(self):
        self.reward_money = 0
        self.reward_karma = 2
        self.reward_relation_hirer = 5

    def init_delivery_set(self):
        # Тут гененрация посылок
        delivery_set = []
        choice = random.choice(self.delivery_set_list[0])
        item = choice.instantiate(amount=choice.amount)
        delivery_set.append(item)
        self.delivery_set = delivery_set

        # Тут гененрация ненужных вещей
        loot_set = []
        randomize_loot = self.loot_set_list[0]
        for i in range(random.choice([1, 2])):  # 1-2 предмета
            choice = random.choice(randomize_loot)
            item = choice.instantiate(amount=choice.amount)
            loot_set.append(item)
        self.loot_set = loot_set

    def init_target_point(self):
        base_point = random.choice(self.cache_points_generator)
        self.cache_point = MarkerMapObject(position=base_point.generate_random_point(), radius=self.cache_radius)

    def init_distance(self):
        p1 = self.hirer.hometown.position.as_point()
        p2 = self.cache_point.position.as_point()
        return p1.distance(p2) * 2  # дистация двойная, так как нужно съездить туда и обратно

    def init_deadline(self, distance):
        # Время выделенное на квест в секундах
        if self.design_speed:
            all_time = int(distance / self.design_speed)
            # Время выделенное на квест кратно 5 минутам
            self.deadline = (all_time / 300) * 300 + (300 if (all_time % 300) > 0 else 0)
        else:
            self.deadline = 0

    def init_text(self):
        self.text_short = LocalizedString(
            en=u"Найти пропавшую посылку.",  # TODO: ##LOCALIZATION
            ru=u"Найти пропавшую посылку.",
        )

        self.text = LocalizedString(
            en=u"Вернуть пропавшую посылку.{} Награда: {:.0f}nc, {:.0f} кармы и {:.0f} ед. опыта.".format(  # TODO: ##LOCALIZATION
                u"." if not self.deadline else u" за {}.".format(self.deadline_to_str()),
                self.reward_money,
                self.reward_karma,
                self.reward_exp,
            ),
            ru=u"Вернуть пропавшую посылку.{} Награда: {:.0f}nc, {:.0f} кармы и {:.0f} ед. опыта.".format(
                u"." if not self.deadline else u" за {}.".format(self.deadline_to_str()),
                self.reward_money,
                self.reward_karma,
                self.reward_exp,
            ),
        )


    def create_poi_container(self, event):
        if self.deadline:
            life_time = self.starttime + self.deadline - event.time
        else:
            life_time = event.server.poi_loot_objects_life_time
        private_name = self.agent.profile._agent_model and self.agent.profile._agent_model.print_login() or self.agent.login

        items = []
        item = self.delivery_set[0].instantiate(amount=self.delivery_set[0].amount)
        items.append(ItemState(server=event.server, time=event.time, example=item, count=item.amount))
        self.dc.package_uid = item.uid
        for item_example in self.loot_set:
            item = item_example.instantiate(amount=item_example.amount)
            items.append(ItemState(server=event.server, time=event.time, example=item, count=item.amount))

        CreatePOILootEvent(
            server=event.server,
            time=event.time,
            poi_cls=QuestPrivatePOILoot,
            example=None,
            inventory_size=len(self.delivery_set) + len(self.loot_set),
            position=Point.random_gauss(self.cache_point.position.as_point(), self.cache_point.radius),
            life_time=life_time,
            items=items,
            connect_radius=0,
            extra=dict(private_name=private_name),
        ).post()

    def can_take_package(self, event):
        if not self.agent.profile.car:
            return False
        if self.agent.profile._agent_model:
            self.agent.profile._agent_model.inventory.save_to_example(time=event.time)
        return self.agent.profile.car.inventory.get_item_by_uid(uid=self.dc.package_uid) is not None

    def take_items_package(self, event):
        if not self.can_take_package(event=event):
            return False
        item = self.agent.profile.car.inventory.get_item_by_uid(uid=self.dc.package_uid)
        self.agent.profile.car.inventory.items.remove(item)
        if self.agent.profile._agent_model:
            self.agent.profile._agent_model.reload_inventory(time=event.time, save=False)
        return True

    def as_client_dict(self):
        d = super(DeliveryFromCache, self).as_client_dict()
        d.update(
            package_example=self.delivery_set[0].as_client_dict() if self.delivery_set and len(self.delivery_set) > 0 else None,
            package_uid=getattr(self.dc, 'package_uid', None)
        )
        return d

    ####################################################################################################################
    def on_generate_(self, event, **kw):
        if not self.can_generate(event):
            raise Cancel("QUEST CANCEL: reason: generate rules")

        if not self.delivery_set_list:
            raise Cancel("QUEST DeliveryFromCache CANCEL: Empty empty delivery_set_list.")
        if self.hirer.hometown is None:
            raise Cancel("QUEST DeliveryFromCache CANCEL: {} hometown is None.".format(self.hirer.hometown))

        self.init_level()
        self.init_delivery_set()
        self.init_target_point()

        distance = self.init_distance()
        if distance == 0:
            log.warning('DeliveryFromCache Quest: Warning!!! Distance from hirer<{}> to point<{}> = {}'.format(self.hirer, self.cache_point, distance))
        self.init_deadline(distance)

        self.generate_reward()  # Устанавливаем награду за квест (карму, деньги и итемы)
        self.init_text()  # Инициализируем строку описания квеста

    ####################################################################################################################
    def on_start_(self, event, **kw):
        if self.get_available_lvl() < self.level:
            self.npc_replica(npc=self.hirer, replica=self.locale("q_dfc_npc_fail"), event=event)  # TODO: ##LOCALIZATION
            raise Cancel("QUEST DeliveryFromCache CANCEL: User have not enough relation")
        self.log(text=self.locale("q_dfc_started"), event=event, position=self.hirer.hometown.position)  # TODO: ##LOCALIZATION

    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.dc.cache_map_note_uid = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.MapMarkerNote,
                time=event.time,
                position=quest.cache_point.position,
                radius=quest.cache_point.radius
            )
            if quest.deadline:
                quest.set_timer(event=event, name='deadline_delivery_cache_quest', delay=quest.deadline)
            quest.set_timer(event=event, name='test_delivery_cache_quest', delay=5)

        def on_event_(self, quest, event):
            agent = quest.agent
            go = partial(quest.go, event=event)
            set_timer = partial(quest.set_timer, event=event)

            if isinstance(event, OnCancel):
                agent.profile.del_note(uid=quest.dc.cache_map_note_uid, time=event.time)
                agent.profile.set_relationship(time=event.time, npc=quest.hirer, dvalue=-quest.reward_relation_hirer)
                quest.log(text='{} {}.'.format(quest.locale("q_dfc_relations"), quest.hirer.title), event=event,  #LOCALIZATION
                          position=quest.hirer.hometown.position)
                go("cancel_fail")
            if isinstance(event, OnTimer):
                if event.name == 'deadline_delivery_cache_quest':
                    agent.profile.del_note(uid=quest.dc.cache_map_note_uid, time=event.time)
                    go("fail")
                if event.name == 'test_delivery_cache_quest':
                    if agent.profile._agent_model and agent.profile._agent_model.car and quest.cache_point.is_near(
                            agent.profile._agent_model.car.position(time=event.time)):
                        agent.profile.del_note(uid=quest.dc.cache_map_note_uid, time=event.time)
                        go("cache")
                    else:
                        set_timer(name='test_delivery_cache_quest', delay=5)

    class cache(QuestState_):
        def on_enter_(self, quest, event):
            # создать лут с временем жизни до окончания дедлайна и с нужными итемами
            quest.create_poi_container(event)
            quest.log(text=quest.locale("q_dfc_find_package"), event=event, position=quest.cache_point.position)  #LOCALIZATION

            # создать ноту на доставку
            quest.dc.delivery_note_uid = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.NPCDeliveryNotePackage,
                time=event.time,
                npc=quest.hirer,
                page_caption=quest.caption,
            )

        def on_event_(self, quest, event):
            agent = quest.agent
            go = partial(quest.go, event=event)

            if isinstance(event, OnCancel):
                quest.npc_replica(npc=quest.hirer, replica=quest.locale("q_dfc_cancel_fail"), event=event)  #LOCALIZATION

            if isinstance(event, OnTimer) and event.name == 'deadline_delivery_cache_quest':
                agent.profile.del_note(uid=quest.dc.delivery_note_uid, time=event.time)
                go("fail")

            if isinstance(event, OnNote):
                if ((event.note_uid == quest.dc.delivery_note_uid) and (event.result == True) and
                        quest.take_items_package(event=event)):
                    agent.profile.del_note(uid=quest.dc.delivery_note_uid, time=event.time)
                    go('reward')

    ####################################################################################################################
    class reward(QuestState_):
        def on_enter_(self, quest, event):
            go = partial(quest.go, event=event)
            agent_profile = quest.agent.profile
            agent_profile.set_exp(time=event.time, dvalue=quest.reward_exp)
            agent_profile.set_karma(time=event.time, dvalue=quest.reward_karma)
            agent_profile.set_relationship(time=event.time, npc=quest.hirer, dvalue=quest.reward_relation_hirer)
            go('win')

    ####################################################################################################################
    class cancel_fail(FailByCancelState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_dfc_fail"), event=event)  #LOCALIZATION

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=quest.locale("q_dfc_win"), event=event)  #LOCALIZATION

    ####################################################################################################################
    class fail(FailState):
        def on_enter_(self, quest, event):
            quest.agent.profile.set_relationship(time=event.time, npc=quest.hirer, dvalue=-20)  # изменение отношения c нпц
            quest.agent.profile.set_karma(time=event.time, dvalue=-10)  # изменение кармы
            quest.log(text=quest.locale("q_dfc_fail"), event=event)  #LOCALIZATION


