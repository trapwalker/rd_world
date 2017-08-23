# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_server.model.quest_events import OnCancel, OnTimer, OnNote
from sublayers_server.model.poi_loot_objects import CreatePOICorpseEvent
from sublayers_server.model.inventory import ItemState
from sublayers_server.model.registry_me.tree import RegistryLinkField, ListField, EmbeddedNodeField, StringField
from sublayers_server.model.registry_me.classes import notes
from sublayers_server.model.registry_me.classes.quests import (
    Cancel,   QuestState_, FailByCancelState, FailState, WinState,
)

from sublayers_world.registry.quests.delivery_from_cache import DeliveryFromCache

import random
from functools import partial
from ctx_timer import T


class SearchCourier(DeliveryFromCache):
    courier_car_list = ListField(
        caption=u"Список возможных машин курьера",
        field=RegistryLinkField(),
    )

    courier_medallion = EmbeddedNodeField(
        document_type='sublayers_server.model.registry_me.classes.quest_item.QuestItem',
        caption=u"Медальон курьера",
        tags={'client'},
    )

    def init_delivery_set(self, event):
        self.delivery_set = []
        # Тут гененрация ненужных вещей
        loot_set = []
        randomise_loot_list = self.loot_set_list[0]
        for i in range(random.choice([1, 2])):  # 1-2 предмета
            # Выбор только по первому элементу списка (т.к. в простой реализации квеста есть только 1 список итемов, а не пресеты)
            choice = random.choice(randomise_loot_list)
            item = choice.instantiate(amount=choice.amount)
            loot_set.append(item)
        self.loot_set = loot_set

        # Выбор машинки курьера
        car = random.choice(self.courier_car_list)
        self.dc.courier_car_uri = car.uri
        #try:
        #    car = event.server.reg.get(car)
        #except:
        #    raise Cancel("QUEST CANCEL: uri<{}>  not resolve.".format(uri))


    def init_text(self):
        self.text_short = u"Найти пропавшего курьера."
        self.text = u"Найти пропавшего курьера и вернуть важный предмет{} Награда: {:.0f}nc, {:.0f} кармы и {:.0f} ед. опыта.".format(
            u"." if not self.deadline else u" за {}.".format(self.deadline_to_str()),
            self.reward_money,
            self.reward_karma,
            self.reward_exp,
        )

    def create_poi_container(self, event):
        # info: так как фишка выпадает сразу, то трупу машинки не нужно ждать до окончания квеста
        # if self.deadline:
        #     life_time = self.starttime + self.deadline - event.time
        # else:
        life_time = event.server.poi_loot_objects_life_time

        items = []
        for item_example in self.loot_set:
            item = item_example.instantiate(amount=item_example.amount)
            items.append(ItemState(server=event.server, time=event.time, example=item, count=item.amount))

        medallion = self.courier_medallion.instantiate()
        self.dc.medallion_uid = medallion.uid
        self.agent.profile.quest_inventory.add_item(agent=self.agent, item=medallion, event=event)
        self.log(text=u'Получена платиновая фишка. Вернитесь в город для завершения квеста.', event=event, position=self.cache_point.position)

        # info: Сделано для того, чтобы работали старые квесты, когда в dc хранился courier_car
        courier_car = getattr(self.dc, 'courier_car', None) or event.server.reg.get(self.dc.courier_car_uri)

        CreatePOICorpseEvent(
            server=event.server,
            time=event.time,
            example=None,
            inventory_size=len(self.loot_set),
            position=self.cache_point.position.as_point(),
            life_time=life_time,
            items=items,
            sub_class_car=courier_car.sub_class_car,
            car_direction=0,
            donor_v=0,
            donor_example=courier_car,
            agent_viewer=None,
        ).post()

    def take_medallion(self, event):
        medallion = self.agent.profile.quest_inventory.get_item_by_uid(self.dc.medallion_uid)
        # todo: medallion не может не быть, если его нет то хз вообще как
        if medallion:
            self.agent.profile.quest_inventory.del_item(agent=self.agent, item=medallion, event=event)
        return True

    ####################################################################################################################
    def on_generate_(self, event, **kw):
        if not self.can_generate(event):
            raise Cancel("QUEST CANCEL: reason: generate rules")
        if self.hirer.hometown is None:
            raise Cancel("QUEST SearchCourier CANCEL: {} hometown is None.".format(self.hirer.hometown))


        if not self.courier_car_list:  # первый раз почему-то долгая операция. Дальше быстрее.
            raise Cancel("QUEST SearchCourier CANCEL: Empty courier_car_list.")

        self.init_level()
        self.init_delivery_set(event=event)
        self.init_target_point()

        distance = self.init_distance()
        if distance == 0:
            log.warning('SearchCourier Quest: Warning!!! Distance from hirer<{}> to point<{}> = {}'.format(self.hirer, self.cache_point, distance))
        self.init_deadline(distance=distance)

        self.generate_reward()  # Устанавливаем награду за квест (карму, деньги и итемы)
        self.init_text()  # Инициализируем строку описания квеста

    ####################################################################################################################
    def on_start_(self, event, **kw):
        if self.get_available_lvl() < self.level:
            self.npc_replica(npc=self.hirer, replica=u"NPC не достаточно хорошо к Вам относится.", event=event)
            raise Cancel("QUEST SearchCourier CANCEL: User have not enough relation")
        self.log(text=u'Начат квест по поиску пропавшего курьера.', event=event, position=self.hirer.hometown.position)

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
                quest.log(text=u'Испорчены отношения с {}.'.format(quest.hirer.title), event=event,
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
            quest.log(text=u'Найдена машина курьера.', event=event, position=quest.cache_point.position)
            quest.create_poi_container(event)

            # создать ноту на доставку
            quest.dc.delivery_note_uid = quest.agent.profile.add_note(
                quest_uid=quest.uid,
                note_class=notes.NPCDeliveryNoteCourier,
                time=event.time,
                npc=quest.hirer,
                page_caption=quest.caption,
            )

        def on_event_(self, quest, event):
            agent = quest.agent
            go = partial(quest.go, event=event)

            if isinstance(event, OnCancel):
                quest.npc_replica(npc=quest.hirer, replica=u"Вы нашли машину курьера и не можете отказаться.", event=event)

            if isinstance(event, OnTimer) and event.name == 'deadline_delivery_cache_quest':
                agent.profile.del_note(uid=quest.dc.delivery_note_uid, time=event.time)
                go("fail")

            if isinstance(event, OnNote):
                if (event.note_uid == quest.dc.delivery_note_uid) and (event.result == True) and quest.take_medallion(
                        event=event):
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
            quest.log(text=u'Квест провален.', event=event)

    ####################################################################################################################
    class win(WinState):
        def on_enter_(self, quest, event):
            quest.log(text=u'Квест выполнен.', event=event)

    ####################################################################################################################
    class fail(FailState):
        def on_enter_(self, quest, event):
            quest.agent.profile.set_relationship(time=event.time, npc=quest.hirer, dvalue=-20)  # изменение отношения c нпц
            quest.agent.profile.set_karma(time=event.time, dvalue=-10)  # изменение кармы
            quest.log(text=u'Квест провален.', event=event)

