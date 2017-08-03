# -*- coding: utf-8 -*-

import logging
log = logging.getLogger(__name__)

from sublayers_server.model.registry_me.classes.quests import Quest


class AIActionQuest(Quest):
    def use_heal(self, time):
        agent_model = self.agent and self.agent.profile._agent_model
        if not agent_model:
            return
        car = agent_model.car
        if not car:
            return
        inventory = car.inventory
        if not inventory:
            return
        from sublayers_server.model.events import ItemPreActivationEvent
        # Найти любую аптечку в инвентаре и использовать её
        position = None
        for item_rec in inventory.get_all_items():
            if item_rec["item"].example.is_ancestor(agent_model.server.reg.get('/registry/items/usable/build_set')):
                position = item_rec["position"]
        if position:
            ItemPreActivationEvent(agent=agent_model, owner_id=car.uid, position=position, target_id=car.uid, time=time).post()

    def is_target(self, target):
        agent_model = self.agent and self.agent.profile._agent_model
        if agent_model:
            return target.uid in agent_model.target_uid_list
        return False
