from esframework import *
def greaterthan(x,y) : return x>=y
def lesserthan(x,y) : return  x<=y
def eq(x,y) : return x==y
def define_contexts(sh):
    sh.define_context(Context('material',goals=['name']))

def define_params(sh):
    materials = ["steel-aisi-1020","steel-aisi-4140","Al-6061","epoxy+0.7glass-fiber"]
    sh.define_param(Parameter('name','material',enum=materials))
    sh.define_param(Parameter('working-stress','material',cls=float,ask_first=True))
    sh.define_param(Parameter('specific-gravity','material',cls=float))
    sh.define_param(Parameter('cost-per-unit-strength','material',cls=float))
def define_rules(sh):
    sh.define_rule(Rule(1,  [
                            ('working-stress','material',lesserthan,70),
                            ('specific-gravity','material',lesserthan,2.11),
                            ('cost-per-unit-strength','material',greaterthan,2.26)
                            ],
                            [('name','material',eq,"epoxy+0.7glass-fiber")],
                            0.11))
    sh.define_rule(Rule(2,  [
                            ('working-stress','material',lesserthan,222),
                            ('cost-per-unit-strength','material',greaterthan,1.07)
                            ],
                            [('name','material',eq,"steel-aisi-4140")],
                            0.3))
    sh.define_rule(Rule(3,  [ ('working-stress','material',lesserthan,117)],
                            [('name','material',eq,"steel-aisi-1020")],
                            0.4))
    sh.define_rule(Rule(4,  [
                            ('working-stress','material',lesserthan,93),
                            ('specific-gravity','material',lesserthan,3),
                            ('cost-per-unit-strength','material',greaterthan,1.6)
                            ],
                            [('name','material',eq,'Al-6061')],
                            0.19))
                            
    
