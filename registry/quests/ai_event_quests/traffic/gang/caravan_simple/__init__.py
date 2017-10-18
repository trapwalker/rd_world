# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_world.registry.quests.ai_event_quests.traffic.gang import AIGangQuest
from sublayers_server.model.registry_me.tree import EmbeddedDocumentField, IntField, ListField, RegistryLinkField
from sublayers_server.model.registry_me.classes.quests import QuestState_, QuestRange
from sublayers_server.model.registry_me.randomize_examples import RandomizeExamples
from sublayers_server.model.vectors import Point
from sublayers_server.model.quest_events import OnTimer
from sublayers_server.model.party import Party
from sublayers_server.model.ai_dispatcher import AIAgent
from sublayers_server.model.registry_me.classes.agents import Agent as AgentExample

from ctx_timer import Timer
from functools import partial
import random
from math import pi

from datetime import datetime, timedelta


class AICaravanQuest(AIGangQuest):
    caravan_wait_time = IntField(root_default=30, caption=u"Задержка перед стартом каравана")
    party_capacity = IntField(root_default=10, caption=u"Вместительность пати каравана с учётом НПЦ")
    radius_participation = IntField(root_default=1000, caption=u"Двойной радиус действия гвардов и одинарный участия игроков")
    town_destination = RegistryLinkField(caption=u'Город назначения каравана')

    count_guardians = EmbeddedDocumentField(document_type=QuestRange, caption=u"Количество защитников")
    cars_guardians = ListField(
        root_default=list,
        caption=u'Список машинок',
        field=RegistryLinkField(document_type='sublayers_server.model.registry_me.classes.mobiles.Car'),
    )

    schedule = ListField(root_default=list, caption=u'Расписание запуска караванов', field=IntField())


    def tags_str(self):
        return '; '.join(list(self.tag_set))

    def get_nearest_time(self, time, schedule, distance):
        curent_time = datetime.fromtimestamp(time)
        day_zero = curent_time.replace(hour=0, minute=0, second=0, microsecond=0)  # Начало суток
        day_zero_seconds = (day_zero - datetime.fromtimestamp(0)).total_seconds()
        day_seconds = (curent_time - day_zero).total_seconds()  # Сколько сейчас прошло секунд с начала суток
        new_time_start = None
        for sh in schedule:
            if 0 < sh - day_seconds < distance:
                time_candidate = day_zero_seconds + sh
                if not new_time_start or new_time_start > time_candidate:
                    new_time_start = time_candidate
        return new_time_start

    def can_instantiate(self, event, agent, hirer=None):
        # Проверка по расписанию. Если мы за caravan_wait_time до ближайшего времени, то Создать квест
        time_start_candidate = self.get_nearest_time(time=event.time, schedule=self.schedule, distance=self.caravan_wait_time)
        if not time_start_candidate:  # Если нет подходящего времени
            return False

        if agent.profile._agent_model.tempd.get(('AICaravanQuest', self.tags_str(), time_start_candidate), None):
            return False
        return super(AICaravanQuest, self).can_instantiate(event=event, agent=agent, hirer=hirer)

    def on_see_object(self, event):  # Вызывается когда только для OnAISee
        return

    def average_caravan_position(self, time):
        traders_car = [agent.car for agent in self.dc.traders if agent.car and not agent.car.limbo]
        if traders_car:
            p = Point(0, 0)
            for car in traders_car:
                p = p + car.position(time)
            return p / len(traders_car)
        else:
            return self.dc.route.get_current_point()

    def set_actions(self, time):  # Настройка поведеньческих квестов
        # Корректируем скорость группы (вдруг самый медленный сдох)
        self.set_main_cc()
        # Определяем есть ли цель

        targets = self.get_visible_targets()
        guardians_target = None
        guardians_cc = 0.8
        if targets:
            guardians_cc = 1.0  # если мы видим когото то ездим активнее
            guardians_target = self.dc.target
            current_target_point = self.average_caravan_position(time=time)
            if current_target_point:
                # Если текущая цель сдохла или уехала за радиус нашей активности то бросить её
                if (not guardians_target or
                        (guardians_target not in targets) or
                        (current_target_point.distance(guardians_target.position(time=time)) > self.dc.guardians_radius)):
                    guardians_target = None

                # Если нет текущей цели то выбрать случайную из тех что в области нашей активноси
                if not guardians_target:
                    potential_targets = [target for target in targets
                                         if current_target_point.distance(target.position(time=time)) <= self.dc.guardians_radius]
                    if potential_targets:
                        guardians_target = random.choice(potential_targets)
            else:
                guardians_target = None

        self.dc.target = guardians_target
        for agent in self.dc.guardians:
            action_quest = agent.action_quest
            if not action_quest or not agent.car or agent.car.limbo:
                continue
            action_quest.dc.target_car = guardians_target
            action_quest.dc.current_cc = guardians_cc

    def test_party(self):
        members = self.dc.members
        if members:
            party = members[0].party
            if party:
                for agent in members:
                    if party is not agent.party:
                        return False
                return True
        return False

    def include_to_party(self, model_agent, event):
        # log.debug('AICaravanQuest:: Try Include to party: %s    %s    %s', model_agent, self.dc.agents_on_party, self.party_capacity)
        if self.dc.agents_on_party >= self.party_capacity:
            return False
        if self.dc.party is not None:
            self.dc.agents_on_party += 1
            self.dc.party.invite(sender=self.dc.party.owner, recipient=model_agent, time=event.time + 0.02)
            self.dc.party.include(agent=model_agent, time=event.time + 0.1)
            return True
        else:
            log.warning('AICaravanQuest::include_to_party:: Party not found!')

    def exclude_from_party(self, model_agent, event):
        self.dc.agents_on_party -= 1
        self.dc.agents_on_party = max(self.dc.agents_on_party, 0)
        # log.debug('AICaravanQuest::exclude_from_party: %s ', self.dc.agents_on_party)

    def deploy_one_agent(self, event, level, additional_agent_params):
        example_profile = RandomizeExamples.get_random_agent(
            level=level, time=event.time, karma_min=self.bots_karma.min, karma_max=self.bots_karma.max,
            agent_params=additional_agent_params)
        example_agent = AgentExample(login='', user_id='', profile=example_profile)
        model_agent = AIAgent(example=example_agent, user=None, time=event.time, server=event.server)
        model_agent.event_quest = self
        return model_agent

    def deploy_one_car(self, event, cars, level, loot_rec_list, start_point_route, action_quest_proto, model_agent):
        car_pos = Point.random_gauss(start_point_route, 30)
        action_quest = action_quest_proto.instantiate(abstract=False, hirer=None, towns_protect=self.towns_protect,
                                                min_wait_car_time=int(self.dc.start_caravan_deadline * 1.5))  # Чтобы квест не сфейлился сразу
        action_quest.dc.current_target_point = start_point_route
        model_agent.create_ai_quest(time=event.time, action_quest=action_quest)

        car_example = RandomizeExamples.get_random_car_level(
            cars=cars,
            level=level,
            car_params=dict(
                position=car_pos,
                direction=random.random() * 2 * pi,
            )
        )
        car_example.pre_buy_car(example_agent=model_agent.example)
        model_agent.example.profile.car = car_example
        self.init_bot_inventory(car_example=car_example, loot_rec_list=loot_rec_list)

    def deploy_traders(self, event):
        # Метод деплоя агентов на карту. Вызывается на on_start квеста
        if not self.routes:
            return

        proto_action_quest = event.server.reg.get('/registry/quests/ai_action_quest/traffic')
        route = random.choice(self.routes).instantiate(route_accuracy=200)
        self.dc.route = route
        start_point_route = route.nearest_point(route.get_start_point().as_point())
        level = self.bots_level.get_random_int()
        self.dc.party = None
        additional_agent_params = dict(party_capacity_count=self.party_capacity)

        for i in range(0, self.dc.count_members):
            model_agent = self.deploy_one_agent(event=event, level=level, additional_agent_params=additional_agent_params)
            self.deploy_one_car(event=event, level=level, loot_rec_list=self.loot_rec_list,
                                start_point_route=start_point_route,
                                cars=self.cars,
                                action_quest_proto=proto_action_quest, model_agent=model_agent)

            self.dc.members.append(model_agent)
            self.dc.traders.append(model_agent)

            if self.dc.party is not None:
                self.include_to_party(model_agent=model_agent, event=event)
            else:
                p_mame = model_agent.print_login().split('_')[0]
                description = "{}'s caravan to {}".format(p_mame, 'ttttt')
                self.dc.party = Party(time=event.time, owner=model_agent, name=p_mame, description=description, exp_share=True)
                self.dc.agents_on_party = 1
                # log.debug('AICaravanQuest:: Create Party %s   owner=%s', self.dc.party, model_agent)

        for i in range(0, self.dc.count_guardians):
            model_agent = self.deploy_one_agent(event=event, level=level, additional_agent_params=additional_agent_params)
            self.deploy_one_car(event=event, level=level, loot_rec_list=None,
                                start_point_route=start_point_route,
                                cars=self.cars_guardians,
                                action_quest_proto=proto_action_quest, model_agent=model_agent)

            self.dc.members.append(model_agent)
            self.dc.guardians.append(model_agent)

            if self.dc.party is not None:
                self.include_to_party(model_agent=model_agent, event=event)
            else:
                log.debug('AICaravanQuest::deploy_guardians:: Party not found!')

    def deploy_cars_on_map(self, event):
        # Метод деплоя агентов на карту. Вызывается на on_start квеста
        for agent in self.dc.members:
            agent.generate_car(time=event.time, car_example=agent.example.profile.car)

    def displace_bots(self, event):
        # Роспуск пати, затем displace_bots
        party = self.dc.party
        if party is not None:
            party_agents = [m.agent for m in party.members]
            for agent in party_agents:
                party.on_exclude(agent=agent, time=event.time)
        else:
            log.warning('AICaravanQuest::displace_bots:: Party not found!')
        self.agent.profile._agent_model.tempd[('AICaravanQuest', self.tags_str(), self.dc.start_caravan_time)] = None
        super(AICaravanQuest, self).displace_bots(event=event)

    ####################################################################################################################
    def on_generate_(self, event, **kw):
        self.dc.start_caravan_time = self.get_nearest_time(time=event.time, schedule=self.schedule, distance=self.caravan_wait_time)
        self.agent.profile._agent_model.tempd[('AICaravanQuest', self.tags_str(), self.dc.start_caravan_time)] = True
        # log.debug('AICaravanQuest::on_generate_::formed: tags=%s  time=%s', self.tags_str(), self.dc.start_caravan_time)
        super(AICaravanQuest, self).on_generate_(event=event, **kw)


    ####################################################################################################################
    def on_start_(self, event, **kw):
        super(AICaravanQuest, self).on_start_(event=event, **kw)
        self.dc.start_caravan_deadline = self.dc.start_caravan_time - event.time
        self.dc.agents_on_party = 0  # Текущее количество агентов в пати
        self.dc.count_guardians = self.count_guardians.get_random_int()
        if self.party_capacity < self.dc.count_members + self.dc.count_guardians:  # Если вместимость пати меньше, чем планируемый размер каравана
            self.party_capacity = self.dc.count_members + self.dc.count_guardians  # info: Защита от дурака
        self.dc.guardians_radius = self.radius_participation / 2.0
        self.dc.guardians = []
        self.dc.traders = []
        self.deploy_traders(event=event)

    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class pre_begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.agent.profile._agent_model.on_event_quest(time=event.time, quest=quest)
            # log.debug('Caravan started in: %ss', quest.dc.start_caravan_deadline)
            quest.set_timer(event=event, name='start_caravan', delay=quest.dc.start_caravan_deadline)

        def on_event_(self, quest, event):
            if isinstance(event, OnTimer) and event.name == 'start_caravan':
                if not quest.test_party():
                    log.warning('=====!!!!!======!!!!!=====  Not All members in Party  ====!!!===')
                quest.go(new_state='run', event=event)

    class run(QuestState_):
        def on_enter_(self, quest, event):
            quest.agent.profile._agent_model.on_event_quest(time=event.time, quest=quest)
            quest.set_timer(event=event, name='test_end', delay=quest.test_end_time)
            quest.deploy_cars_on_map(event=event)

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            if isinstance(event, OnTimer) and (event.name == 'test_end'):
                status = quest.get_traffic_status(event)
                if status == 'win':
                    quest.displace_bots(event)
                    go('win')
                elif status == 'fail':
                    quest.displace_bots(event)
                    go('fail')
                else:
                    quest.set_timer(event=event, name='test_end', delay=quest.test_end_time)
                    quest.set_actions(time=event.time)
                    quest.set_target_point(time=event.time)
    ####################################################################################################################


