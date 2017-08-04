# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_world.registry.quests.ai_event_quests import AIEventQuest
from sublayers_server.model.registry_me.tree import (IntField, ListField, RegistryLinkField, EmbeddedNodeField)
from sublayers_server.model.registry_me.classes.quests import (
    QuestState_, FailState, WinState,
)
from sublayers_server.model.quest_events import OnTimer
from sublayers_server.model.vectors import Point

from functools import partial
import random
from math import pi


class AITrafficQuest(AIEventQuest):
    test_end_time = IntField(caption=u'Интервал проверки достижения цели')
    routes = ListField(
        root_default=list,
        caption=u"Список маршрутов",
        field=EmbeddedNodeField(
            document_type='sublayers_server.model.registry_me.classes.routes.Route',
        ),
    )

    towns_protect = ListField(
        root_default=list,
        caption=u"Список городов покровителей",
        field=RegistryLinkField(
            document_type='sublayers_server.model.registry_me.classes.poi.Town',
        ),
    )

    def instantiate_agent(self, event, agent_proto):
        example_profile = agent_proto.instantiate(
            name='',
            role_class=random.choice(event.server.reg.get('/registry/world_settings').role_class_order or ['/registry/rpg_settings/role_class/chosen_one']),
        )

        example_profile.set_karma(time=event.time, value=random.randint(-30, 60))

        example_profile.driving.value = max(example_profile.driving.value + random.randint(-5, 5), 0)
        example_profile.shooting.value = max(example_profile.shooting.value + random.randint(-5, 5), 0)
        example_profile.masking.value = max(example_profile.masking.value + random.randint(-5, 5), 0)
        example_profile.leading.value = max(example_profile.leading.value + random.randint(-5, 5), 0)
        example_profile.trading.value = max(example_profile.trading.value + random.randint(-5, 5), 0)
        example_profile.engineering.value = max(example_profile.engineering.value + random.randint(-5, 5), 0)

        points = example_profile.driving.value + example_profile.shooting.value + example_profile.masking.value + example_profile.leading.value + example_profile.trading.value + example_profile.engineering.value
        exp = example_profile.exp_table.get_need_exp_by_points(points - example_profile.role_class.start_free_point_perks)
        example_profile.set_exp(time=event.time, value=exp)
        return example_profile

    def deploy_bots(self, event):
        # Метод деплоя агентов на карту. Вызывается на on_start квеста
        from sublayers_server.model.ai_dispatcher import AIAgent
        from sublayers_server.model.registry_me.classes.agents import Agent as AgentExample

        if not self.routes or not self.cars:
            return

        car_proto = random.choice(self.cars).instantiate()
        route = random.choice(self.routes).instantiate()
        self.dc.route = route
        example_profile = event.server.reg.get('/registry/agents/user/ai_quest')
        action_quest = event.server.reg.get('/registry/quests/ai_action_quest/traffic')

        example_profile = self.instantiate_agent(event, example_profile)

        # todo: сделать несколько видов профилей ботов, чтобы там были прокачаны скилы и перки
        example_agent = AgentExample(
            login='',
            user_id='',
            profile=example_profile,
        )

        self.dc._main_agent = AIAgent(
            example=example_agent,
            user=None, time=event.time, server=event.server
        )
        self.dc._main_agent.event_quest = self
        action_quest = action_quest.instantiate(abstract=False, hirer=None, towns_protect=self.towns_protect)
        action_quest.dc.current_target_point = self.dc.route.get_start_point().as_point()
        self.dc._main_agent.create_ai_quest(time=event.time, action_quest=action_quest)
        car_example = car_proto.instantiate(
            position=Point.random_gauss(route.get_start_point().as_point(), 30),
            direction=random.random() * 2 * pi,
        )
        self.init_bot_inventory(car_example=car_example)
        self.dc._main_agent.generate_car(time=event.time, car_example=car_example)

        # log.debug('Quest {!r} deploy_bots: {!r}'.format(self, self.dc._main_agent))

    def displace_bots(self, event):
        # Метод удаления с карты агентов-ботов. Вызывается на при завершении квеста
        main_agent = getattr(self.dc, '_main_agent', None)
        if main_agent:
            main_agent.displace(time=event.time)
            self.dc._main_agent = None
            log.debug('Quest {!r} displace bots: {!r}'.format(self, main_agent))

    def get_traffic_status(self, event):
        main_agent = getattr(self.dc, '_main_agent', None)
        if main_agent and main_agent.car is None:
            return 'fail'
        if main_agent and main_agent.action_quest and main_agent.action_quest.status == 'end':
            # спросить у квеста, пройден ли он и если да, то вернуть 'win'
            return main_agent.action_quest.result

    def on_see_object(self, event):  # Вызывается когда только для OnAISee
        self_karma = self.dc._main_agent.example.profile.karma_norm
        if self_karma > 0.3:  # Не добавляет, если карма хорошая
            return
        obj = getattr(event, 'obj', None)
        if obj is None:
            return
        agent = getattr(obj, 'main_agent', None)
        if not agent:
            return
        if abs(agent.example.profile.karma_norm - self_karma) > 0.3:
            # Добавить во враги
            damager_uid = obj.uid
            if damager_uid not in self.dc.target_uid_list:
                self.dc.target_uid_list.append(damager_uid)

    def get_visible_targets(self):
        r = []
        agent_vo = self.dc._main_agent.get_all_visible_objects()
        for target_uid in self.dc.target_uid_list:
            for vo in agent_vo:
                if target_uid == vo.uid:
                    r.append(vo)
        return r

    def get_total_hp(self, cars, time):
        hp = 0
        for car in cars:
            hp += car.hp(time)
        return hp

    def get_total_dps(self, cars):
        dps = 0
        for car in cars:
            dps += car.get_total_dps()
        return dps

    def get_power_ratio(self, targets, time):
        team_hp = self.get_total_hp(cars=[self.dc._main_agent.car], time=time)
        enemy_hp = self.get_total_hp(cars=targets, time=time)
        team_dps = self.get_total_dps(cars=[self.dc._main_agent.car])
        enemy_dps = self.get_total_dps(cars=targets)
        if enemy_dps == 0:
            return 10
        if team_dps == 0:
            return 0
        return (team_hp / enemy_dps) / (enemy_hp / team_dps)

    def set_actions(self, time):  # Настройка поведеньческих квестов
        targets = self.get_visible_targets()
        action_quest = self.dc._main_agent.action_quest
        if not action_quest or not self.dc._main_agent.car or self.dc._main_agent.car.limbo:
            return
        # Нет видимых целей, значит ехать по маршруту
        if not targets:
            action_quest.dc.target_car = None
            action_quest.dc.current_cc = 0.5
            return
        # Определение run или attacke
        action_quest.dc.current_cc = 1.0
        if self.get_power_ratio(targets=targets, time=time) > 1.0:
            # todo: Выбрать цель для атаки  (Учесть расстояние, хп цели, свою скорость)
            if not action_quest.dc.target_car or action_quest.dc.target_car not in targets:
                action_quest.dc.target_car = random.choice(targets)
        else:
            # Убегать
            action_quest.dc.target_car = None


####################################################################################################################

    def set_target_point(self, time):
        car = self.dc._main_agent.car
        if not car or car.limbo:
            # self.dc._main_agent.action_quest.dc.current_target_point = None
            return
        car_pos = self.dc._main_agent.car.position(time)
        if self.dc.route.need_next_point(car_pos):
            self.dc._main_agent.action_quest.dc.current_target_point = self.dc.route.next_point()

    def on_generate_(self, event, **kw):
        pass

    ####################################################################################################################
    def on_start_(self, event, **kw):
        self.dc.target_uid_list = []
        self.deploy_bots(event=event)

    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class begin(QuestState_):
        def on_enter_(self, quest, event):
            quest.set_timer(event=event, name='test_end', delay=quest.test_end_time)

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent
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
    class win(WinState):pass
    ####################################################################################################################
    class fail(FailState):pass
    ####################################################################################################################