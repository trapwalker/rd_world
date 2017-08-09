# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_world.registry.quests.ai_event_quests.traffic import AITrafficQuest
from sublayers_server.model.registry_me.classes.quests import QuestRange
from sublayers_server.model.registry_me.tree import EmbeddedDocumentField
from sublayers_server.model.vectors import Point

from sublayers_server.model.registry_me.randomize_examples import RandomizeExamples

from ctx_timer import Timer, T
from functools import partial
import random
from math import pi


class AIGangQuest(AITrafficQuest):
    count_members = EmbeddedDocumentField(document_type=QuestRange, caption=u"Количество участников")

    def deploy_bots(self, event):
        # Метод деплоя агентов на карту. Вызывается на on_start квеста
        from sublayers_server.model.ai_dispatcher import AIAgent
        from sublayers_server.model.registry_me.classes.agents import Agent as AgentExample

        if not self.routes:
            return

        action_quest = event.server.reg.get('/registry/quests/ai_action_quest/traffic')
        route = random.choice(self.routes).instantiate(route_accuracy=200)
        self.dc.route = route
        start_point_route = route.nearest_point(route.get_start_point().as_point())
        level = random.randint(self.bots_level.min, self.bots_level.max)

        timer_summ_agent = 0
        timer_summ_car = 0
        timer_summ_quest = 0

        timer_summ_agent_ex_profile = 0
        timer_summ_agent_ex_agent = 0
        timer_summ_agent_model = 0

        timer_summ_car_ex = 0
        timer_summ_car_inv = 0

        with Timer(name='Deploy') as deploy_timer:
            for i in range(0, self.dc.count_members):
                with Timer(name='Agent') as deploy_agent_timer:
                    with Timer(name='Agent_ex_pr') as deploy_summ_agent_ex_profile_timer:
                        example_profile = RandomizeExamples.get_random_agent(level=level, time=event.time, karma_min=self.bots_karma.min, karma_max=self.bots_karma.max)
                    timer_summ_agent_ex_profile += deploy_summ_agent_ex_profile_timer.duration

                    with Timer(name='Agent_ex_agent') as deploy_timer_summ_agent_ex_agent:
                        example_agent = AgentExample(login='', user_id='', profile=example_profile)
                    timer_summ_agent_ex_agent += deploy_timer_summ_agent_ex_agent.duration

                    with Timer(name='Agent_ex_agent') as deploy_timer_summ_agent_model:
                        model_agent = AIAgent(example=example_agent, user=None, time=event.time, server=event.server)
                    timer_summ_agent_model += deploy_timer_summ_agent_model.duration
                timer_summ_agent += deploy_agent_timer.duration

                model_agent.event_quest = self

                with Timer(name='Quest') as deploy_quest_timer:
                    car_pos = Point.random_gauss(start_point_route, 30)
                    action_quest = action_quest.instantiate(abstract=False, hirer=None, towns_protect=self.towns_protect)
                    action_quest.dc.current_target_point = start_point_route
                    model_agent.create_ai_quest(time=event.time, action_quest=action_quest)
                timer_summ_quest += deploy_quest_timer.duration

                with Timer(name='Car') as deploy_car_timer:
                    with Timer(name='Car') as deploy_timer_summ_car_ex:
                        car_example = RandomizeExamples.get_random_car_level(
                            level=level,
                            car_params=dict(
                                position=car_pos,
                                direction=random.random() * 2 * pi,
                                base_exp_price=self.bots_car_exp.get_random_int(),
                            )
                        )
                    timer_summ_car_ex += deploy_timer_summ_car_ex.duration

                    with Timer(name='Car') as deploy_timer_summ_car_inv:
                        self.init_bot_inventory(car_example=car_example)
                    timer_summ_car_inv += deploy_timer_summ_car_inv.duration

                    model_agent.generate_car(time=event.time, car_example=car_example)
                timer_summ_car += deploy_car_timer.duration

                self.dc.members.append(model_agent)
        log.debug("Deploy Gang: {} members =>>> {:.4f}s".format(self.dc.count_members, deploy_timer.duration))
        log.debug("Agents: {:.4f}s     Quests: {:.4f}s     Cars: {:.4f}s".format(timer_summ_agent, timer_summ_quest, timer_summ_car))

        log.debug("Agents: Profile {:.4f}s     Example: {:.4f}s     Model: {:.4f}s".format(timer_summ_agent_ex_profile, timer_summ_agent_ex_agent, timer_summ_agent_model))
        log.debug("Cars: Example {:.4f}s     Inventory: {:.4f}s".format(timer_summ_car_ex, timer_summ_car_inv))

    def displace_bots(self, event):
        # Метод удаления с карты агентов-ботов. Вызывается на при завершении квеста
        for agent in self.dc.members:
            agent.displace(time=event.time)
        # log.debug('Quest {!r} displace bots: {!r}'.format(self, len(self.dc.members)))
        self.dc.members = []

    def get_traffic_status(self, event):
        for agent in self.dc.members:
            if agent and (agent.action_quest.status == 'active'):
                return None
        return 'fail'

    def on_see_object(self, event):  # Вызывается когда только для OnAISee
        obj = getattr(event, 'obj', None)
        if obj is None:
            return
        if not getattr(obj, 'main_agent', None):
            return
        if not self.is_observer(obj):
            return
        # Добавить во враги
        obj_uid = obj.uid

        if obj_uid in [agent.car.uid for agent in self.dc.members if agent.car and not agent.car.limbo]:
            return

        if obj_uid not in self.dc.target_uid_list:
            self.dc.target_uid_list.append(obj_uid)

    def set_main_cc(self):
        min_v = min([agent.car._param_aggregate['v_forward'] for agent in self.dc.members if agent.car and not agent.car.limbo])
        for agent in self.dc.members:
            if agent.car and not agent.car.limbo:
                agent.action_quest.current_cc = agent.car.get_cc_by_speed(speed=min_v)

    def get_visible_targets(self):
        r = []
        for agent in self.dc.members:
            agent_vo = agent.get_all_visible_objects()
            for target_uid in self.dc.target_uid_list:
                for vo in agent_vo:
                    if (target_uid == vo.uid) and (vo not in r):
                        r.append(vo)
        return r

    def get_power_ratio(self, targets, time):
        team_car_list = [agent.car for agent in self.dc.members if agent.car and not agent.car.limbo]
        team_hp = self.get_total_hp(cars=team_car_list, time=time)
        enemy_hp = self.get_total_hp(cars=targets, time=time)
        team_dps = self.get_total_dps(cars=team_car_list)
        enemy_dps = self.get_total_dps(cars=targets)
        if enemy_dps == 0:
            return 10
        if team_dps == 0:
            return 0
        return (team_hp / enemy_dps) / (enemy_hp / team_dps)

    def set_actions(self, time):  # Настройка поведеньческих квестов
        # Корректируем скорость группы (вдруг самый медленный сдох)
        self.set_main_cc()

        # Определяем есть ли цель
        targets = self.get_visible_targets()
        if self.get_power_ratio(targets=targets, time=time) > 1.0:
            if not self.dc.target or self.dc.target not in targets:
                if targets:
                    self.dc.target = random.choice(targets)
                else:
                    self.dc.target = None

        for agent in self.dc.members:
            action_quest = agent.action_quest
            if not action_quest or not agent.car or agent.car.limbo:
                continue
            action_quest.dc.target_car = self.dc.target

    def set_target_point(self, time):
        next_point = True
        route = self.dc.route
        for agent in self.dc.members:
            if agent.car and not agent.car.limbo and not route.need_next_point(agent.car.position(time)):
                next_point = False
                break

        if next_point:
            new_target = route.next_point()
        else:
            new_target = route.get_current_point()

        for agent in self.dc.members:
            if agent.car and not agent.car.limbo:
                if new_target:
                    agent.action_quest.dc.current_target_point = Point.random_gauss(new_target, 100)
                else:
                    agent.action_quest.dc.current_target_point = None

    ####################################################################################################################
    def on_start_(self, event, **kw):
        self.dc.count_members = self.count_members.get_random_int()
        self.dc.members = []
        self.dc.target = None
        super(AIGangQuest, self).on_start_(event=event, **kw)