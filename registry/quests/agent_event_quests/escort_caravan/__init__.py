# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)

from sublayers_world.registry.quests.agent_event_quests import AgentEventQuest
from sublayers_world.registry.quests.ai_event_quests.traffic.gang.caravan_simple import AICaravanQuest
from sublayers_server.model.quest_events import OnTimer, OnPartyExclude
from sublayers_server.model.registry_me.classes.quests import Cancel
from sublayers_server.model.registry_me.tree import LocalizedString

from functools import partial


class EscortCaravan(AgentEventQuest):
    def as_unstarted_quest_dict(self):
        d = super(EscortCaravan, self).as_unstarted_quest_dict()
        d.update(start_quest_time=getattr(self.dc, 'start_caravan_time', None))
        return d

    def init_text(self, event, event_quest):
        town = event_quest.town_destination
        town_str = town and town.title or 'N'
        self.text_short = LocalizedString(
            en=u"Сопроводите караван.",  # TODO: ##LOCALIZATION
            ru=u"Сопроводите караван.",
        )
        self.text = LocalizedString(
            en=u"Сопроводите караван в город {}. Награда: {:.0f}nc.".format(town_str, self.reward_money),  # TODO: ##LOCALIZATION
            ru=u"Сопроводите караван в город {}. Награда: {:.0f}nc.".format(town_str, self.reward_money),
        )


    def get_potential_event_quest(self, event, agent):
        event_quests = event.server.ai_dispatcher.get_quest_by_tags(set(self.needed_tags))
        npc_view_quests = agent.profile.npc_view_quests
        for event_quest in event_quests:
            flag = False
            for agent_quest in npc_view_quests:
                if isinstance(agent_quest, AgentEventQuest) and (
                                agent_quest.event_quest_uid == str(event_quest.uid) or  # Если квест на такой караван уже есть у агента
                                event_quest.dc.start_caravan_time <= event.time):  # или Если караван уже уехал
                    flag = True
                    break
            if not flag:
                return event_quest
        return None

    def can_generate(self, event):
        if not super(EscortCaravan, self).can_generate(event=event):
            return False
        event_quest = self.get_event_quest(event=event)

        if event_quest and isinstance(event_quest, AICaravanQuest) and event.time < event_quest.dc.start_caravan_time:
            self.shelf_life_time = event_quest.dc.start_caravan_time - event.time
            self.dc.start_caravan_time = event_quest.dc.start_caravan_time
        else:
            return False
        return True

    def on_generate_(self, event, **kw):
        super(EscortCaravan, self).on_generate_(event=event, **kw)
        event_quest = self.get_event_quest(event=event)
        if event_quest:
            self.init_text(event=event, event_quest=event_quest)

    def calc_participation(self, car_pos, caravan_pos):
        try:
            if car_pos.distance(caravan_pos) <= self.dc.radius_participation:
                self.dc.count_participation += 1.0
        except:
            log.error('!!!!!!!!!!!!!!!!==============   car_pos=%s,   caravan_pos=%s', car_pos, caravan_pos)
            pass

    ####################################################################################################################
    def on_start_(self, event, **kw):
        self.dc.check_participation = 0.0
        self.dc.count_participation = 0.0
        self.dc.caravan_started = False
        event_quest = self.get_event_quest(event=event)
        if event_quest and self.agent.profile._agent_model:
            res = event_quest.include_to_party(model_agent=self.agent.profile._agent_model, event=event)
            if not res:
                self.npc_replica(
                    npc=self.hirer,
                    replica=LocalizedString(
                        en=u"Караван сформирован.",  # TODO: ##LOCALIZATION
                        ru=u"Караван сформирован.",
                    ),
                    event=event,
                )
                raise Cancel("QUEST CANCEL: Caravan Party is full.")
            self.dc.radius_participation = event_quest.radius_participation

    ####################################################################################################################
    class begin(AgentEventQuest.begin):
        def on_enter_(self, quest, event):
            super(EscortCaravan.begin, self).on_enter_(quest=quest, event=event)
            quest.set_timer(event=event, name='participation', delay=30)
            quest.log(
                LocalizedString(
                    en=u'Ожидание каравана.',  # TODO: ##LOCALIZATION
                    ru=u'Ожидание каравана.',
                ),
                event=event,
            )

        def on_event_(self, quest, event):
            super(EscortCaravan.begin, self).on_event_(quest=quest, event=event)
            if isinstance(event, OnTimer) and event.name == 'participation':
                quest.set_timer(event=event, name='participation', delay=30)
                event_quest = quest.get_event_quest(event=event)
                if event_quest:
                    agent_model = quest.agent.profile._agent_model
                    if event_quest.current_state == 'run':  # Если караван в пути
                        if not quest.dc.caravan_started:
                            quest.dc.caravan_started = True
                            quest.log(
                                LocalizedString(
                                    en=u'Караван выехал.',  # TODO: ##LOCALIZATION
                                    ru=u'Караван выехал.',
                                ),
                                event=event,
                            )
                        caravan_point = event_quest.average_caravan_position(time=event.time)
                        if caravan_point:
                            quest.dc.check_participation += 1.0
                            if agent_model and agent_model.car and not agent_model.car.limbo:
                                quest.calc_participation(car_pos=agent_model.car.position(event.time), caravan_pos=caravan_point)

            if isinstance(event, OnPartyExclude) and event.agent and event.agent is quest.agent.profile._agent_model:
                # Отказ от квеста (будто у нпц отказался)
                quest.go(new_state='cancel_fail', event=event)
                event_quest = quest.get_event_quest(event=event)
                if event_quest:
                    event_quest.exclude_from_party(model_agent=event.agent, event=event)

    ####################################################################################################################
    class win(AgentEventQuest.win):
        def on_enter_(self, quest, event):
            if quest.dc.check_participation == 0:
                quest.dc.check_participation = 1.0

            participation = quest.dc.count_participation / quest.dc.check_participation
            quest.log(
                LocalizedString(
                    en=u'Участие в караване: {}%'.format(int(100 * participation)),  # TODO: ##LOCALIZATION
                    ru=u'Участие в караване: {}%'.format(int(100 * participation)),
                ),
                event=event,
            )
            super(EscortCaravan.win, self).on_enter_(quest=quest, event=event)

            agent_profile = quest.agent.profile
            agent_profile.set_exp(time=event.time, dvalue=int(quest.reward_exp * participation))
            agent_profile.set_karma(time=event.time, dvalue=quest.reward_karma * participation)
            agent_profile.set_relationship(time=event.time, npc=quest.hirer, dvalue=int(quest.reward_relation_hirer * participation))
            agent_profile.set_balance(time=event.time, delta=int(quest.reward_money * participation))

    ####################################################################################################################
    class cancel_fail(AgentEventQuest.cancel_fail):
        def on_enter_(self, quest, event):
            super(EscortCaravan.cancel_fail, self).on_enter_(quest=quest, event=event)

            event_quest = quest.get_event_quest(event=event)
            if event_quest and event_quest.dc.party is not None and quest.agent.profile._agent_model in event_quest.dc.party:
                event_quest.dc.party.on_exclude(agent=quest.agent.profile._agent_model, time=event.time)
                event_quest.exclude_from_party(model_agent=quest.agent.profile._agent_model, event=event)

            quest.log(
                LocalizedString(
                    en=u'Отказ от участия в караване.',  # TODO: ##LOCALIZATION
                    ru=u'Отказ от участия в караване.',
                ),
                event=event,
            )
            quest.agent.profile.set_relationship(time=event.time, npc=quest.hirer, dvalue=-5)  # изменение отношения c нпц
            quest.agent.profile.set_karma(time=event.time, dvalue=-5)  # изменение кармы
