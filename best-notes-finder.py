#!/usr/bin/env python
# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import optparse
import threading
import Queue
import urllib2


START_ID = 277436060
END_ID = 277436070
NUM_WORKER = 3


class ResultWriter(threading.Thread):
    def __init__(self, filename, result_queue):
        threading.Thread.__init__(self)
        self.daemon = True

        self.filename = filename
        self.result_queue = result_queue

    def run(self):
        try:
            with open(self.filename, 'a') as f:
                while True:
                    result_line = self.result_queue.get()
                    f.write("{0}\n".format(result_line))
                    f.flush
                    self.result_queue.task_done()
        except Exception as e:
            print '[Error] Exception - {}'.format(str(e))
            exit(0)


class FinderWorker(threading.Thread):
    def __init__(self, id_queue, result_queue):
        threading.Thread.__init__(self)
        self.daemon = False

        self.id_queue = id_queue
        self.result_queue = result_queue

    def run(self):
        while True:
            try:
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
                print '[+] {0} liked by {1} people'.format(id, fav_num)

            except urllib2.HTTPError as e:
                print '[-] {0} {1}'.format(id, str(e))
            except Queue.Empty:
                print '[Info] Queue empty, worker stop.'
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
        # wait for the id_queue to be empty
        id_queue.join()

        print '[Info] Main(): Finished!'
    except KeyboardInterrupt:
        print '[Interrupted] Exit()'
        exit(0)


if __name__ == '__main__':
    main()

