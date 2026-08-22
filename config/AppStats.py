''''*******************************************************************************************************************
* Copyright         : Iktara Data Sciences
* File Name         : AppStats.py
* Description       : Functions related to statistics and counters
*
* Revision History  :
* Date				Author    		        Comments
* ---------------------------------------------------------------------------------------------------------------------
* 02-Sept-25		Aniket Kaushik		     Created.
*
*********************************************************************************************************************'''

from CommonUtils.stats.StatsMgr import cutil_init_counters, cutil_get_stats

DATAFLOW_SUCCESS_STATS = 0
DATAFLOW_FAILURE_STATS = 1

APP_LOCAL_MAX_COUNTERS = 2


def appstats_init_counter_config():
    counter_config = {

        DATAFLOW_SUCCESS_STATS: {
            'CounterName': 'DataflowSuccess_total',
            'CounterDesc': 'Total number of successful dataflows',
            'Owner': True
        },
        DATAFLOW_FAILURE_STATS: {
            'CounterName': 'DataflowFailure_total',
            'CounterDesc': 'Total number of failed dataflows',
            'Owner': True
        }
    }
    return counter_config


def appstats_get_counter_data(counter_type, start_date, end_date, step_size):
    if counter_type > APP_LOCAL_MAX_COUNTERS:
        return None
    if app_counter_config[counter_type]['Owner']:
        counter_name = str(app_counter_config[counter_type]['CounterName'])
    else:
        counter_name = str(app_counter_config[counter_type]['CounterName'])
    df_stats = cutil_get_stats(counter_name, start_date, end_date, step_size)
    return df_stats


def appstats_inc_counter(counter_type, count_val):
    global counter_list
    if counter_type <= APP_LOCAL_MAX_COUNTERS:
        counter_list[counter_type].inc(count_val)
    return


# Initialize Global counter Config
app_counter_config = appstats_init_counter_config()

# Create and Initialise Local Counters
counter_list = cutil_init_counters(app_counter_config)


