#!/usr/bin/env python
# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import time
import optparse
import threading
import Queue
import urllib2


START_ID = 277400000
END_ID = 277499999
NUM_WORKER = 20
FORBIDDEN_ALERT_LEVEL = 5
FORBIDDEN_SLEEP_SECONDS = 120


class ResultWriter(threading.Thread):
    def __init__(self, filename, result_queue):
        threading.Thread.__init__(self)
        self.daemon = False

        self._stop = False

        self.filename = filename
        self.result_queue = result_queue

    def stop(self):
        self._stop = True

    def stopped(self):
        return self._stop

    def run(self):
        try:
            # open to write with line-buffer (1)
            with open(self.filename, 'a', 1) as f:
                while True:
                    # test if stop signal has been received
                    if self.stopped() == True:
                        print '\n[Info] Writer thread is stopped according to notification.'
                        break;
                    
                    try:
                        result_line = self.result_queue.get(block = True, timeout = 5)
                        f.write("{0}\n".format(result_line))
                        f.flush
                        self.result_queue.task_done()
                    except Exception:
                        pass

        except Exception as e:
            print '\n[Error] Exception - {}'.format(str(e))
            exit(0)


class FinderWorker(threading.Thread):
    def __init__(self, id_queue, result_queue):
        threading.Thread.__init__(self)
        self.daemon = False

        self.id_queue = id_queue
        self.result_queue = result_queue

        self._stop = False

        self._forbidden_alert = 0
        self._forbidden_ids = []

    def stop(self):
        self._stop = True

    def stopped(self):
        return self._stop

    def clear_forbidden_status(self):
        self._forbidden_alert = 0
        self._forbidden_ids[:] = []

    def run(self):
        while True:
            try:
                # test if stop signal has been received
                if self.stopped() == True:
                    print '\n[Info] Worker thread is stopped according to notification.'
                    break;

                # get id from queue and wait for at most 3 seconds
                id = self.id_queue.get(block = True, timeout = 3)

                # Tell the quene we have done with id
                self.id_queue.task_done()

                url = 'http://www.douban.com/note/{}/'.format(id)
                usock = urllib2.urlopen(url)
                data = usock.read()
                usock.close()
                fav_num = self.getFavNumFromHTML(data)
                self.result_queue.put('{0},{1}'.format(id, fav_num))
                print '\n[+] {0} liked by {1} people'.format(id, fav_num)

            except urllib2.HTTPError as e:
                print '.',
                
                # handle requests forbidden
                if 'Forbidden' in str(e):
                    print '\n[-] {0} {1}'.format(id, str(e))
                    self._forbidden_alert += 1
                    self._forbidden_ids.append(id)
                    if self._forbidden_alert >= FORBIDDEN_ALERT_LEVEL:
                        print '\n[ALERT] Forbidden Alert! Sleeping for {} seconds!'.format(FORBIDDEN_SLEEP_SECONDS)
                        time.sleep(FORBIDDEN_SLEEP_SECONDS)
                        
                        # return forbidden ids to queue
                        for id in self._forbidden_ids:
                            self.id_queue.put(id)

                        # clear
                        self.clear_forbidden_status()
                else:
                    self.clear_forbidden_status()

            except Queue.Empty:
                print '\n[Info] Queue empty, worker stop.'
                break;
    
    def getFavNumFromHTML(self, html_string):
        soup = BeautifulSoup(html_string)
        try:
            fav_num_string = soup.find('span', {'class' : 'fav-num'}).find('a').string
            return int(fav_num_string[:-1])
        except AttributeError as e:
            return 0


def main():
    # get target file path
    parser = optparse.OptionParser('usage %prog -o <target file>')
    parser.add_option('-o', dest='filename', type='string', help='specify target file')
    (options, args) = parser.parse_args()
    filename = options.filename
    if filename == None:
        print parser.usage
        exit(0)

    id_queue = Queue.Queue()
    result_queue = Queue.Queue()

    # fill id_queue
    for i in range(START_ID, END_ID):
        id_queue.put(i)

    # start result writer
    writer = ResultWriter(filename, result_queue)
    writer.start()

    # start worker
    worker_list = []
    for i in range(0, NUM_WORKER):
        worker = FinderWorker(id_queue, result_queue)
        worker_list.append(worker)
        worker.start()

    try:
        # wait...
        while True:
            time.sleep(5)
            for w in worker_list:
                if w.isAlive() == True:
                    break
            else:
                # all workers have finished, quit
                break

        print '\n[Info] Main(): Finished!'

    except KeyboardInterrupt:
        print '\n[Interrupted] Notifying workers and writer to quit...'
        for w in worker_list:
            w.stop()
        writer.stop()


if __name__ == '__main__':
    main()

