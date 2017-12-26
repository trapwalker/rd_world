# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_server.model.quest_events import OnTimer, OnQuestOut, OnQuestSee, OnAppendCar, OnDie, OnGetDmg
from sublayers_server.model.registry_me.classes.quests import (
    QuestState_, FailState, WinState,
)
from sublayers_server.model.registry_me.tree import (RegistryLinkField, ListField, IntField)

from sublayers_world.registry.quests.ai_action_quest import AIActionQuest
from sublayers_server.model.vectors import Point

from functools import partial


class AIActionTrafficQuest(AIActionQuest):
    min_wait_car_time = IntField(root_default=10, caption='Минимальное время ожидания появления машинки')

    towns_protect = ListField(
        root_default=list,
        caption=u"Список городов покровителей (Устанавливается квестом-событием)",
        reinst=True,
        field=RegistryLinkField(
            document_type='sublayers_server.model.registry_me.classes.poi.Town',
        ),
    )

    def __str__(self):
        return '{}[{}|{}|({})]'.format(self.__class__.__name__, self.node_hash(), self.current_state, self.dc.current_target_point)

    def discharge_shoot_command(self, event):
        agent_model = self.agent.profile._agent_model
        car = agent_model.car if agent_model else None
        if not car:
            return
        event_quest = agent_model.event_quest
        target_uid_list = event_quest.dc.target_uid_list
        for sector in car.fire_sectors:
            if sector.is_discharge():
                for target_uid in target_uid_list:
                    target = event.server.objects.get(target_uid, None)
                    if target and event_quest.is_observer(target) and event_quest.is_see_object(target) and sector._test_target_in_sector(target=target, time=event.time):
                        car.fire_discharge(side=sector.side, time=event.time)

    def towns_aggro(self, event):
        pass  # 20-10-17 - отключен агр городов за атаку по городским мобам
        # agent = getattr(event, 'obj', None) and event.obj.main_agent
        # if not agent:
        #     return
        # from sublayers_server.model.map_location import Town
        # for town in Town.get_towns():
        #     if town.example in self.towns_protect:
        #         town.on_enemy_candidate(agent=agent, damage=True, time=event.time)

    def set_motion(self, car, cc, target_point, event):
        if cc != self.dc.last_cc or target_point != self.dc.last_target_point or event.time - self.dc.last_time_set_motion > 20:
            car.set_motion(time=event.time, cc=cc, target_point=target_point)
            self.dc.last_cc = cc
            self.dc.last_target_point = target_point
            self.dc.last_time_set_motion = event.time

    def get_target_point(self, event):
        target_car = self.dc.target_car
        if target_car and not target_car.limbo:
            return Point.random_gauss(target_car.position(event.time), 20)
        # взять из роута квеста эвента
        return self.dc.current_target_point

    ####################################################################################################################
    def on_generate_(self, event, **kw):
        pass
    
    ####################################################################################################################
    def on_start_(self, event, **kw):
        self.dc.target_car = None  # Переопределяется квестом-событием
        self.dc.current_target_point = self.get_target_point(event)  # Переопределяется квестом-событием
        self.dc.current_cc = 0.5  # Переопределяется квестом-событием
        self.dc.last_cc = 0.0
        self.dc.last_target_point = None
        self.dc.last_time_set_motion = event.time - 5.0
    
    ####################################################################################################################
    ## Перечень состояний ##############################################################################################
    class wait_car(QuestState_):
        def on_enter_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent
            if agent.profile._agent_model.car:
                go('patrol')
            else:
                quest.set_timer(event=event, name='wait_car', delay=quest.min_wait_car_time)
    
        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent
            if isinstance(event, OnAppendCar) and agent.profile._agent_model.car:
                go('patrol')
            if isinstance(event, OnTimer) and event.name == 'wait_car':
                if agent.profile._agent_model.car:
                    go('patrol')
                else:
                    go('fail')

    ####################################################################################################################
    class patrol(QuestState_):
        def on_enter_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent
            car = agent.profile._agent_model.car
            if car:
                target_pos = quest.get_target_point(event=event)
                if target_pos:
                    quest.set_motion(car=car, cc=quest.dc.current_cc, target_point=target_pos, event=event)
                    quest.set_timer(event=event, name='patrol', delay=5)
                else:
                    go('win')
            else:
                log('Car for agent {} not found'.format(agent.login))
                go('fail')

        def on_event_(self, quest, event):
            go = partial(quest.go, event=event)
            agent = quest.agent
            if isinstance(event, OnTimer) and event.name == 'patrol':
                car = agent.profile._agent_model.car
                if car:
                    quest.set_timer(event=event, name='patrol', delay=3)
                    # Хил по необходимости
                    if car.hp(time=event.time) < 20:
                        quest.use_heal(time=event.time)

                    target_pos = quest.get_target_point(event=event)
                    if target_pos:
                        quest.set_motion(car=car, cc=quest.dc.current_cc, target_point=target_pos, event=event)
                    else:
                        go('win')

                    quest.discharge_shoot_command(event=event)

                else:
                    log('Car for agent {} not found'.format(agent.login))
                    go('fail')

            if isinstance(event, OnDie):
                go('fail')

            if isinstance(event, OnGetDmg):
                quest.towns_aggro(event=event)

            if isinstance(event, OnQuestSee) and agent.profile._agent_model.event_quest:
                agent.profile._agent_model.event_quest.on_see_object(event=event)

    ####################################################################################################################
    class win(WinState):pass
    ####################################################################################################################
    class fail(FailState):pass
    ####################################################################################################################